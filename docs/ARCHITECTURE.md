# Architecture

The system is layered front-to-back with hard rules at every seam.
This doc walks the request flow, the data model, and the design
decisions that are easy to miss in a code skim.

## Request flow — happy path

```
1. Browser → Caddy (TLS 1.3) → reverse_proxy api:8000
2. RequestContextMiddleware       attaches request_id (UUIDv6) + IP/UA
3. SecurityHeadersMiddleware       sets HSTS, frame-options, CSP
4. CORSMiddleware                  allow_origins=cors_allow_origins
5. Global exception handlers       wrap raised DomainError → envelope
6. Router (apps/api/app/api/v1/)  validates Pydantic body
7. RoleRequired / TokenSubjectDep  decode JWT from cookie, gate access
8. Service                         orchestrates repos + adapters
9. Repository                      DB queries via async session
10. AuditLogRepository.write       in same transaction as the action
11. success_envelope               returns { success, data, request_id }
```

Every layer has a single responsibility and **does not** reach across
seams. Routers don't query the DB. Repositories don't call vendors.
Services don't construct HTTP responses.

## The async accreditation flow

Submission is HTTP-immediate but resolution is asynchronous; the FE
polls. End-to-end:

```
POST /accreditation
  └─ AccreditationService.submit(user, ctx)
       ├─ repo.create(check, status=PENDING, submit_at=now)
       ├─ AuditLogRepository.write(ACCREDITATION_SUBMITTED, status=pending)
       └─ enqueue_accreditation_resolve(check_id, defer_seconds=5)

  ARQ worker fires after the 5s deferral
  └─ resolve_accreditation(check_id)
       ├─ MockAccreditationAdapter.poll(reference)
       ├─ repo.update(status=SUCCESS|FAILED)
       └─ AuditLogRepository.write_independent(ACCREDITATION_RESOLVED)

GET /accreditation  (polled every 2s by FE while pending)
  └─ returns the latest check state
```

The mock adapter is **Redis-backed** so the API and worker (separate
processes) share the pending registry without a DB hit per probe.

## Data model

```
users
  id            UUIDv6 PK
  email         CITEXT UNIQUE
  password_hash TEXT       -- argon2id
  full_name     TEXT
  nationality   CHAR(2)    -- ISO-3166-1 alpha-2
  domicile      CHAR(2)
  phone         TEXT       -- E.164 from phonenumbers
  role          TEXT       -- ENUM: USER | ADMIN
  created_at    TIMESTAMPTZ

refresh_tokens
  id            UUIDv6 PK
  user_id       UUIDv6 FK
  token_hash    TEXT      -- sha256
  family_id     UUIDv6    -- groups rotated tokens
  revoked_at    TIMESTAMPTZ NULL
  expires_at    TIMESTAMPTZ
  created_at    TIMESTAMPTZ

audit_logs
  id            UUIDv6 PK
  timestamp     TIMESTAMPTZ
  user_id       UUIDv6 FK NULL    -- null for pre-auth events
  action        TEXT              -- AUTH_LOGIN | KYC_SUBMIT | ...
  resource_type TEXT NULL
  resource_id   UUIDv6 NULL
  status        TEXT              -- success | failure | pending
  request_id    UUIDv6
  ip            INET NULL
  user_agent    TEXT NULL
  metadata      JSONB NOT NULL    -- small, PII-free
  -- indexes: (user_id, timestamp DESC), (action, timestamp DESC), (request_id)

kyc_checks
  id              UUIDv6 PK
  user_id         UUIDv6 FK
  status          TEXT              -- pending | success | failed | not_started
  attempt         INT               -- 1..N (cap at 3)
  provider        TEXT              -- "mock" today
  provider_ref    TEXT
  failure_reason  TEXT NULL
  raw             JSONB             -- vendor payload (PII-stripped)
  created_at      TIMESTAMPTZ

accreditation_checks   -- same shape as kyc_checks; status flips async

bank_accounts
  id                   UUIDv6 PK
  user_id              UUIDv6 FK
  bank_name            TEXT
  account_holder_name  TEXT
  account_type         TEXT       -- checking | savings | money_market
  last_four            CHAR(4)    -- *only* the masked tail
  currency             CHAR(3)    -- ISO 4217
  mock_balance         NUMERIC(20,4)
  status               TEXT       -- active | unlinked
  linked_at            TIMESTAMPTZ
  unlinked_at          TIMESTAMPTZ NULL
  -- plaintext numbers never reach the DB; they're masked in the request handler

investments
  id                UUIDv6 PK
  user_id           UUIDv6 FK
  bank_account_id   UUIDv6 FK
  amount            NUMERIC(20,4)
  currency          CHAR(3)
  status            TEXT
  escrow_reference  TEXT
  notes             TEXT NULL
  settled_at        TIMESTAMPTZ NULL
  created_at        TIMESTAMPTZ
```

All primary keys are UUIDv6 — sortable (so `ORDER BY id` is roughly
chronological), and the prefix is millisecond-resolution timestamp,
which makes cursor pagination `WHERE id < $cursor` cheap.

Money is `NUMERIC(20, 4)` end-to-end — never `float`. Currency is
always carried alongside the amount as ISO 4217.

## Adapter Protocol pattern

Each external vendor surfaces as a Python `Protocol` in
`apps/api/app/adapters/<vendor>/base.py`. The mock adapter implements
the protocol; tests load a `Fake<Vendor>Adapter` for the same
surface. The DI seam in `apps/api/app/api/deps.py` is where a real
provider would slot in:

```python
class KycProvider(Protocol):
    async def submit_check(
        self, *, user_id: UUID, email: str, full_name: str | None,
        nationality: str | None, domicile: str | None,
    ) -> KycCheckResult: ...
    async def fetch_status(self, *, provider_reference: str) -> KycCheckResult: ...
```

The mock adapters seed deterministic outcomes from email tags
(`+kyc_fail`, `+kyc_pending`, `+acc_fail`, `+bank_fail`) — that's
how the FE Playwright spec exercises every branch without test
state on the backend.

## Auth + session model

- **Argon2id** password hashing (parameters in config).
- **JWT** in **httpOnly cookies** in every environment, including local.
  - `vestrs_access` 15-minute lifetime.
  - `vestrs_refresh` 14-day, **rotated on every use**.
  - In local: `Secure=false`, `SameSite=Lax`. In staging/prod:
  `Secure=true`, `SameSite=Strict`, `Domain=.vestrs.manishlamba.com`.
- **Refresh-token reuse detection.** Every refresh issues a new
family member and revokes the old one. If a *previously-rotated*
token shows up, the entire family is revoked — that's the
steal-and-replay defence.
- **Single vague login error.** `AUTH_INVALID_CREDENTIALS` for both
unknown-email and wrong-password. The audit log records the
specific reason internally for support; the response doesn't,
closing the user-enumeration channel. Constant-ish work on miss
(verify against a sentinel argon2 hash) closes the timing channel.

Full security baseline: [SECURITY.md](SECURITY.md).

## Idempotency on `POST /investments`

The endpoint demands an `Idempotency-Key` header (8–128 ASCII).
Three outcomes:

1. **First-time key** — execute, store `(key, body_hash, response, status)`
  in Redis with 24h TTL, return 201.
2. **Replay with same body** — return the cached envelope from Redis,
  no DB writes; the audit log gets an `INVESTMENT_IDEMPOTENT_REPLAY`
   row (independent session, success).
3. **Replay with different body** — 409 `IDEMPOTENCY_KEY_REUSED`,
  audit log gets `INVESTMENT_BLOCKED` (independent session, failure).

This is verified by the live e2e curl in slice 14B's runbook.

## Rate limiting

Hand-rolled Redis sliding-window in `apps/api/app/core/rate_limit.py`.
Per-IP and per-email on auth endpoints, per-user on
`POST /investments`. Returns 429 with `Retry-After`. Caddy can layer
its own per-IP limiter on top (the staging/prod Caddyfiles ship a
generous global limit; per-route caddy-ratelimit is a slice 19
candidate).

## Audit log invariants

Two write paths:

1. `**AuditLogRepository.write(...)`** — uses the request session,
  commits with the action. Failures of the action would roll this
   row back too — desired for SUCCESS audits.
2. `**AuditLogRepository.write_independent(...)**` — opens a fresh
  session, commits immediately, never participates in the request
   transaction. Used for FAILURE audits so they survive the
   `DomainError` rollback. Also used for idempotency-replay audits
   where the action transaction is "no DB writes".

The `metadata` JSONB column is intentionally small and PII-free
(IDs, status codes, reasons — never raw emails, never full account
numbers).

## Frontend shape

Vite + React 19 SPA. Routes:

```
/                          LandingPage              eager
/login                     LoginForm + side panel   eager
/signup                    SignupForm + side panel  eager
/dashboard                 5-step status board      lazy
/onboarding/profile        form                     lazy
/onboarding/kyc            submit + retry           lazy
/onboarding/accreditation  submit + 2s polling      lazy
/onboarding/bank           link / unlink            lazy
/onboarding/invest         amount + idempotent send lazy
/audit                     cursor-paginated feed    lazy
*                          NotFound                 eager
```

Public routes ship in the entry chunk so the cold paint is fast.
Auth-gated routes are split with `React.lazy()` + Suspense; chunks
are 1–14 KB gzipped (slice 17). Vendor libs partitioned into
`react-vendor`, `tanstack-vendor`, `framer-vendor`, `radix-vendor`,
`form-vendor`, `font-vendor` so deploys don't co-invalidate them.

State: TanStack Query with 60s staleTime on `/me`. Forms with
react-hook-form + zod resolvers. Errors flow through `ApiError` →
`error-messages.ts` → user-friendly toast (codes, never raw
messages, never request_id).

Theme: hand-rolled light/dark with single-click toggle, persisted to
localStorage, first-paint inline script in `index.html` to avoid the
flash. Premium typography: Fraunces (display) + Inter (UI), bundled
via `@fontsource-variable` and split into a `font-vendor` chunk.

## Performance budget

- LCP < 1.5s on 4G.
- INP < 200ms.
- Cold landing-page payload (slice 17): ~28 KB entry + ~132 KB
react-vendor gzipped = ~160 KB total. Subsequent visits drop to
~28 KB because vendor chunks are content-hashed and cached.

## Slice journal (selected)

Each slice is a single PR squash-merged into `main`, with a
matching `slice/<NN>-<name>` branch kept around as the build
journal. Highlights:

- **0–3** envelope, middleware, request-id propagation, rate limiter, DB + Alembic.
- **4** auth: argon2id, JWT in httpOnly cookies, refresh-token reuse detection.
- **5** profile (`PUT /users/me`).
- **6** KYC adapter Protocol + mock + retry cap + audit.
- **7** accreditation async resolve via ARQ.
- **8** bank link with masked-only persistence.
- **9** investments with `Idempotency-Key` + balance check + atomic audit.
- **10** audit-read API (cursor pagination, admin scope widening).
- **11** Vite + React Router shell, theme, API client, auth.
- **12** onboarding flow routes + audit feed.
- **13** GitHub Actions: ci, e2e (Playwright), security (Trivy, gitleaks), SonarCloud, branch protection.
- **14A** GHCR release pipeline + staging/prod compose overlays + Caddy.
- **14B** Terraform AWS stack + SSM-triggered deploys + cloud-init + nightly pg_dump.
- **14C** `/metrics` + local Prom/Grafana profile + grafana-agent → Cloud + alert rules.
- **15–17** UX polish: favicon, optimistic top-nav, code-split + vendor chunks.
- **18** this submission README + docs.
