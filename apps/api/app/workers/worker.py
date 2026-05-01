"""ARQ worker — background job runner.

Today the worker only handles accreditation resolution; later slices add more
jobs. The shape stays the same: jobs are pure coroutines that take ``ctx``
plus their own args, with no shared mutable state outside ``ctx``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, ClassVar
from uuid import UUID

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.adapters.accreditation import (
    AccreditationProvider,
    MockAccreditationAdapter,
)
from app.adapters.email import EmailAdapter, NullEmailAdapter, SmtpEmailAdapter
from app.adapters.email.templates import render_welcome_email
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.accreditation import resolve_check

log = get_logger("worker")

# Singleton adapter — same instance the API uses through DI. The worker runs
# in its own process so this is per-process, but for the mock that's fine
# because the registry persists in Redis-backed real adapters anyway.
_provider: AccreditationProvider = MockAccreditationAdapter()


def _build_email_adapter() -> EmailAdapter:
    s = get_settings()
    if not s.smtp_host or not s.smtp_from_address:
        # Local dev / tests / any env where SMTP isn't configured.
        # Don't fail the signup flow just because email is off.
        return NullEmailAdapter()
    return SmtpEmailAdapter(
        host=s.smtp_host,
        port=s.smtp_port,
        username=s.smtp_username,
        password=s.smtp_password,
        use_tls=s.smtp_use_tls,
        from_address=s.smtp_from_address,
        from_name=s.smtp_from_name,
    )


_email_adapter: EmailAdapter = _build_email_adapter()


def _arq_redis_settings() -> RedisSettings:
    s = get_settings()
    return RedisSettings.from_dsn(s.redis_url)


# ---- jobs -----------------------------------------------------------------


async def send_welcome_email(ctx: dict[str, Any], email: str) -> str:
    """Render and send the welcome email. Idempotent at the SMTP level —
    Gmail accepts duplicate sends to the same recipient; we tolerate
    re-runs from arq retries rather than tracking sent state in Redis."""
    settings = get_settings()
    dashboard_url = f"{settings.public_web_url.rstrip('/')}/dashboard"
    message = render_welcome_email(
        recipient_email=email,
        dashboard_url=dashboard_url,
    )
    try:
        await _email_adapter.send(message)
    except Exception as exc:  # log and swallow, email is best-effort
        log.warning("welcome_email_send_failed", error=str(exc))
        return "failed"
    return "sent"


async def resolve_accreditation(ctx: dict[str, Any], check_id: str) -> str:
    """Resolve a pending accreditation check; re-enqueue if still pending."""
    settings = get_settings()
    status, terminal = await resolve_check(
        check_id=UUID(check_id),
        provider=_provider,
    )
    if not terminal:
        # Still pending — re-enqueue with backoff (cap at 5 minutes).
        backoff = min(settings.accreditation_resolution_delay_seconds * 2, 300)
        log.info(
            "accreditation_still_pending_reenqueue",
            check_id=check_id,
            backoff_seconds=backoff,
        )
        pool: ArqRedis = ctx["arq_redis"]
        await pool.enqueue_job(
            "resolve_accreditation",
            check_id,
            _defer_by=timedelta(seconds=backoff),
        )
    return status.value


# ---- worker startup -------------------------------------------------------


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging(get_settings().log_level)
    ctx["arq_redis"] = ctx["redis"]
    log.info("worker_started")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker_stopped")


class WorkerSettings:
    """ARQ entrypoint. Run with:  arq app.workers.WorkerSettings"""

    functions: ClassVar[list[Callable[..., Any]]] = [resolve_accreditation, send_welcome_email]
    redis_settings = _arq_redis_settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    keep_result = 60  # seconds — short, jobs are not user-facing
    max_jobs = 10
    job_timeout = 30
    queue_name = "vestrs:accreditation"


# ---- enqueue helper used from request handlers ----------------------------


async def enqueue_accreditation_resolve(check_id: UUID, *, defer_seconds: int) -> None:
    """Open a fresh ARQ pool, enqueue the job, close. Called from a route
    handler so we don't keep a persistent pool inside the API process."""
    pool = await create_pool(_arq_redis_settings())
    try:
        await pool.enqueue_job(
            "resolve_accreditation",
            str(check_id),
            _defer_by=timedelta(seconds=defer_seconds),
            _queue_name=WorkerSettings.queue_name,
        )
    finally:
        # arq's ArqRedis -> redis-py 5 has aclose() but the typeshed lags;
        # close() works on both, fall back if attribute missing.
        close = getattr(pool, "aclose", None)
        if close is not None:
            await close()
        else:
            await pool.close()


async def enqueue_welcome_email(email: str) -> None:
    """Fire-and-forget welcome email. Called from auth signup. Failure
    here MUST NOT fail the signup — emails are best-effort, signup
    is the source of truth."""
    try:
        pool = await create_pool(_arq_redis_settings())
    except Exception as exc:  # Redis unreachable shouldn't break signup
        log.warning("welcome_email_enqueue_skipped", error=str(exc))
        return
    try:
        await pool.enqueue_job(
            "send_welcome_email",
            email,
            _queue_name=WorkerSettings.queue_name,
        )
    finally:
        close = getattr(pool, "aclose", None)
        if close is not None:
            await close()
        else:
            await pool.close()
