# Security

What this system does to be defensible by default. Keep this doc in
sync with `apps/api/app/core/security.py`,
`apps/api/app/core/middleware.py`, and the Caddyfiles.

## Threat model (sketch)

The interesting traffic is investor sessions: signups, KYC, money
movement. The 1-week demo runs on a public domain with a single
EC2 box and is **not** a hardened production target — it's a
production-shaped take-home. Specifically:

- **In scope**: brute-force login, replay attacks, CORS / CSRF
  attacks, XSS exfil, SQL injection, supply-chain (CVEs), secret
  leakage to git, user enumeration, idempotency replay attacks,
  TLS downgrade, info-leak via error messages.
- **Out of scope** (deferred for the demo): DDoS at L4 (no AWS
  Shield Advanced / WAF in this slice), tenant isolation (single
  Postgres), HSM-grade key custody, anti-money-laundering controls
  beyond the audit log.

## Authentication

- **Argon2id** for passwords. Parameters in `Settings`. Constant-ish
  work on miss (verify against a sentinel argon2 hash) closes the
  timing channel for unknown-email lookups.
- **JWT** in httpOnly cookies, in **every** environment including
  `local` (so the contract is the same). Algorithm: HS256.
- **Access** token: 15-minute lifetime, payload
  `{ sub, jti, iat, exp, type:"access", role }`.
- **Refresh** token: 14-day lifetime, **rotated on every use**.
  Hashed (sha256) at rest in `refresh_tokens`. Each refresh creates
  a new `family_id` member; presenting a previously-rotated token
  triggers **family revocation** — the steal-and-replay defence.
- **Cookie attributes**:
  - local: `Secure=false`, `SameSite=Lax`, host-only.
  - staging/prod: `Secure=true`, `SameSite=Strict`,
    `Domain=.vestrs.manishlamba.com` (so the cookie rides on both
    `vestrs.*` and `api.vestrs.*`).
- **Vague login error**. `AUTH_INVALID_CREDENTIALS` for both
  unknown-email and wrong-password. The audit log records the
  specific reason internally; the response doesn't, closing the
  user-enumeration channel from the login form.
- **Logout** revokes the current refresh family.

## Authorization

- `TokenSubjectDep` decodes the JWT, returns the user's id + role.
- `RoleRequired(Role.ADMIN)` is a factory in `apps/api/app/api/deps.py`
  for endpoints that need admin (e.g. audit-log scope widening to
  `?all=true` or `?user_id=…`).
- Default model: a user can only read / mutate their own resources.
  Repository methods take `user_id` and scope queries with it.

## Audit log

Every state-changing action — login, signup, profile update, KYC
submit/retry, accreditation submit/resolve, bank link/unlink,
investment create/blocked/replay, refresh-token rotate/reuse-detected
— writes a row.

Two write paths (see [ARCHITECTURE.md § Audit log invariants](ARCHITECTURE.md#audit-log-invariants)):

- **Same-transaction** `repo.write(...)` for SUCCESS audits.
- **Independent-session** `repo.write_independent(...)` for FAILURE
  audits, so they survive the `DomainError` rollback.

`metadata` JSONB is small + PII-free (status codes, reasons, IDs,
*never* raw emails, never full account numbers, never JWTs).

Indexes: `(user_id, timestamp DESC)`, `(action, timestamp DESC)`,
`(request_id)`.

## Secrets

- **Never in git.** The pre-commit `gitleaks protect --staged` hook
  + the CI `gitleaks` job over the full PR diff are the two safety
  nets. As of this commit there are no findings across the repo's
  full history.
- **`.env*` files are gitignored**, only `*.example` is tracked. The
  pre-commit hook explicitly blocks committing `.env*` (non-example).
- **Production secrets** live in **AWS SSM Parameter Store** as
  `SecureString` (KMS-encrypted with `aws/ssm`). Cloud-init reads
  them at first boot, writes the rendered `.env.<env>` file to disk
  with `chmod 600`. The script refuses to run without the params.
- **GHCR PAT** is one of those SSM params; the EC2 IAM role's
  inline policy grants `ssm:GetParameter` only on its own
  parameter ARNs, not `*`.

## Network

- **Security Group** opens **80/tcp + 443/tcp from `0.0.0.0/0`**
  only. SSH is **not** open. Operator access is via **AWS SSM
  Session Manager** — auditable, no key pair on the box, no port 22
  in the SG.
- **ufw** as a host-level second wall: `default deny incoming`,
  `default allow outgoing`, only `80` + `443` allowed.
- **fail2ban** tails Caddy's JSON access log; bans IPs after 12×
  401/403/429 in 10 minutes for 15 minutes (slice 14B cloud-init).
- **IMDSv2 required** on the EC2 instance (`http_tokens=required`)
  to close the SSRF→IMDSv1→credentials path.
- **TLS 1.3** via Caddy with auto-renewal. Let's Encrypt HTTP-01
  challenge.

## Edge headers (Caddy)

Both `Caddyfile.staging` and `Caddyfile.prod` set:

- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), camera=(), microphone=(), interest-cohort=()`
- `Content-Security-Policy` — `default-src 'self'`; script-src
  self only; style-src self + `'unsafe-inline'` (Tailwind needs it);
  img/font-src self + data:; `connect-src` pinned to the matching
  API host; `frame-ancestors 'none'`; `form-action 'self'`.
- `Server` header stripped.

## Application input handling

- All Pydantic schemas use `extra="forbid"`. Unknown fields → 422.
- Money is `Decimal` end-to-end. DB stores `NUMERIC(20, 4)`.
  Currency is ISO 4217; nationality / domicile are ISO-3166-1
  alpha-2 (`pycountry`).
- Phone numbers are validated via `phonenumbers` and stored as E.164.
- Bank account / routing numbers are validated for digit-only +
  length, then **masked at the request handler before they reach
  the repository** (only `last_four` is persisted).
- Raw SQL is forbidden outside Alembic migrations. Everything else
  goes through SQLAlchemy parameterized queries.

## Idempotency replay protection

`POST /investments` requires an `Idempotency-Key` (8–128 ASCII).
Three outcomes guard against double-submit:

1. **First time**: execute, store `(user_id, key, body_hash,
   response, status_code)` in Redis with 24h TTL, return 201.
2. **Same key, same body**: replay the cached envelope, audit row
   `INVESTMENT_IDEMPOTENT_REPLAY` (independent session, success).
3. **Same key, different body**: 409 `IDEMPOTENCY_KEY_REUSED`,
   audit row `INVESTMENT_BLOCKED` (independent session, failure).

A serial replay test in `apps/api/tests/integration/test_investments.py`
asserts all three branches.

## CVE policy

- **Trivy** scans every PR (api image + web `dist/` filesystem) and
  every release (api image, again at publish-time). HIGH+CRITICAL
  fail the build by default. SARIF goes to GitHub code scanning.
- **`.trivyignore` policy**: every entry must include a one-line
  justification + a `Re-check by: YYYY-MM-DD` ≤60 days out. The
  weekly Trivy schedule re-fails once a fix lands.
- **Goal**: empty `.trivyignore` is the steady state. As of this
  commit it is empty.
- **`gitleaks`** runs on every PR (full-history) and on the
  pre-commit hook (staged). Both are red on any finding.

## Logging

- `structlog`, JSON to stdout. Required fields: `ts`, `level`,
  `msg`, `request_id`, `route`, `method`, `status`, `latency_ms`,
  `user_id` (nullable), `event`.
- Uvicorn's own access log is disabled — we emit ours.
- **Never logged**: raw passwords, full SSNs/PANs, JWTs, full
  refresh tokens. Emails are masked (`u***@d***.com`); phone last
  4 only; bank account last 4 only.
- Pydantic models with sensitive fields use `SecretStr` and
  `repr=False`.

## Frontend posture

- Errors flow through a typed `ApiError` and the `error-messages.ts`
  code-keyed map. The user-facing toast **never** echoes
  `error.message`, **never** echoes `request_id`. The request_id is
  logged to `console.error` for support correlation.
- The login error is deliberately vague: a single "Invalid email or
  password" message regardless of which side of the pair was wrong.
- SPA routing is React Router; the production bundle has CSP
  `script-src 'self'` so a stored XSS would have to come from
  same-origin code, not an injected `<script>` tag.

## CI security gates (required to merge to `main`)

1. `api · ruff + black + mypy`
2. `api · pytest` (163+ tests, with coverage)
3. `web · eslint + tsc`
4. `web · vitest`
5. `web · vite build` (catches dist regressions)
6. `docker · build api/worker/web`
7. `playwright · happy-path + kyc-failure` (full e2e against compose)
8. `gitleaks · full-history secret scan`
9. `trivy · api image vuln scan`
10. `trivy · web dist filesystem scan`
11. `Trivy` (SARIF code-scanning upload aggregate)
12. `SonarCloud scan`
13. `SonarCloud Code Analysis` (quality gate)

## Deferred / known limits

- **WAF / Shield Advanced** — out of scope for the demo. AWS Shield
  Standard (free, automatic) is on. The runbook documents the
  one-line CloudFront + WAF switch when the time comes.
- **Per-route Caddy rate-limit** — `caddy-ratelimit` plugin would
  layer on top of the FastAPI Redis limiter. Tracked as slice 19.
- **Mimir alert rules sync from CI** — rules live in the repo
  (`infra/observability/grafana/alerts/`); operator runs
  `mimirtool rules sync` for now (slice 14D follow-up).
- **CSP nonces for inline scripts** — the first-paint theme script
  is inline; CSP currently allows `script-src 'self'` and that
  inline script is hashable but not nonce-d. Hardening would add
  per-response nonces via Caddy.
