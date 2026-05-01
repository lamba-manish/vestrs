# Vestrs — Mini Investment Onboarding Platform

> Read this file at the start of every session. It is the source of truth for
> conventions. If a rule blocks a task, raise it before working around it.

## 1. Mission

Cross-border investment onboarding flow:
`signup → KYC/AML/liveness → Accreditation → Bank link → Investment → Audit log`

All third-party vendors (KYC, Accreditation, Bank) are mocked behind adapter
interfaces. Real vendors swap in by replacing the adapter, never the caller.

## 2. Stack

- **Backend**: Python 3.12, FastAPI (async), SQLAlchemy 2 async, Alembic,
  Pydantic v2, structlog, ARQ (Redis-backed worker). **`uv` is the only
  package manager** — never `pip`, `poetry`, or `pipenv`.
- **Frontend**: Vite 5 + React 19 + react-router-dom 7 SPA, TypeScript
  (strict), Tailwind, shadcn/ui-style primitives over Radix, React Hook
  Form + Zod, TanStack Query, Sonner, framer-motion. Built to a static
  `dist/` bundle that Caddy serves directly. No SSR, no Node runtime in
  production — pure static SPA. (We started on Next.js but the Next 15 +
  React 19 + standalone build hit an unworkable upstream bug in the
  synthesised /404 prerender; Vite is simpler and avoids the entire
  prerender concern for an authenticated SPA.)
- **Data**: PostgreSQL 16, Redis 7.
- **Container**: Docker multi-stage, docker-compose.
- **Reverse proxy / TLS**: Caddy (auto-TLS via Let's Encrypt) on every env
  that has a public domain (staging + production).
- **IaC**: Terraform (S3 + DynamoDB remote state). Region `ap-south-1`.
- **CI / quality gates**: GitHub Actions only. Gitleaks (pre-commit + CI).
  SonarCloud (no self-hosted SonarQube). Trivy (container scan). No
  Jenkins.
- **Observability**: Grafana Cloud free tier; `grafana-agent` on the box
  ships metrics + logs. Local Prometheus + Grafana available via a
  `--profile observability` opt-in compose flag for offline development.
- **Hosting**: single **AWS EC2 t3.small (Ubuntu 24.04, ap-south-1)** runs
  everything: Caddy + static FE + FastAPI + ARQ worker + Postgres + Redis
  + grafana-agent. **No Vercel.** Caddy serves the static frontend bundle
  as files and reverse-proxies `/` API hosts to FastAPI.
  - Domain: `manishlamba.com`.
  - Production: FE `https://vestrs.manishlamba.com`, API
    `https://api.vestrs.manishlamba.com` (Swagger at `/docs`),
    monitoring `https://monitoring.vestrs.manishlamba.com`
    (self-hosted Grafana, slice 23).
  - Staging: FE `https://staging.vestrs.manishlamba.com`, API
    `https://staging-api.vestrs.manishlamba.com`.
  - GitHub: `https://github.com/lamba-manish/vestrs`.

## 3. Environments

Three environments, selected by `APP_ENV`:

| Env          | URL                                            | TLS | Cookies                            | Mocks | Logs |
|--------------|------------------------------------------------|-----|------------------------------------|-------|------|
| `local`      | `http://localhost:8000`                        | No  | httpOnly, SameSite=Lax, Secure=0   | On    | debug |
| `staging`    | `https://staging-api.vestrs.manishlamba.com`   | Yes | httpOnly, SameSite=Strict, Secure=1 | On    | info  |
| `production` | `https://api.vestrs.manishlamba.com`           | Yes | httpOnly, SameSite=Strict, Secure=1 | On (assignment scope) | info |

Frontend hosts (static bundle served by Caddy on the same EC2 box):
- `local` → `http://localhost:3000` (Next.js dev server only — production
  build is always `next build && next export` artifact in `apps/web/out/`)
- `staging` → `https://staging.vestrs.manishlamba.com`
- `production` → `https://vestrs.manishlamba.com`

Swagger docs are exposed at `<api>/docs` in **all** environments per the
project owner's request. Note for future hardening: in real production
it should be auth-gated or moved behind an internal-only host. Tracked in
README "deferred hardening".

Every environment has its own `.env.<env>.example`. Real `.env*` files are
gitignored. Never read env vars directly — go through
`app.core.config.Settings` (Pydantic `BaseSettings`).

Both staging and production run on the **same EC2 host**, separated by
docker-compose project name and subdomain. They share the host but **not**
volumes, networks, or DB schemas. Postgres has separate roles + databases
per env.

## 4. Folder layout

```
vestrs/
├── apps/
│   ├── api/                       FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── core/              config, logging, security, errors, middleware
│   │   │   ├── api/v1/            routers (auth, users, kyc, accreditation, bank, investments, audit)
│   │   │   ├── models/            SQLAlchemy ORM models
│   │   │   ├── schemas/           Pydantic request/response
│   │   │   ├── repositories/      DB access only — no business logic
│   │   │   ├── services/          business logic — orchestrates repos + adapters
│   │   │   ├── adapters/          external-API mocks (kyc, accreditation, bank)
│   │   │   ├── workers/           ARQ tasks (poll accreditation, etc.)
│   │   │   └── db/                session, base, alembic env
│   │   ├── alembic/               versions/ committed; runs in every env at boot
│   │   ├── tests/                 unit/, integration/, contract/, conftest.py
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── .env.example
│   └── web/                       Next.js frontend
│       ├── app/                   routes
│       ├── components/            shared UI primitives
│       ├── features/              onboarding, kyc, accreditation, bank, invest
│       ├── lib/                   api client, schemas, hooks
│       ├── tests/                 vitest unit + playwright e2e
│       ├── Dockerfile
│       ├── package.json
│       └── .env.example
├── infra/
│   ├── compose/
│   │   ├── docker-compose.yml         local stack: api, worker, web, db, redis
│   │   ├── docker-compose.staging.yml adds caddy + restart policies
│   │   └── docker-compose.prod.yml    same but stricter
│   ├── caddy/
│   │   ├── Caddyfile.staging
│   │   └── Caddyfile.prod
│   ├── terraform/
│   │   ├── envs/{local,staging,prod}/ tfvars per env
│   │   ├── modules/{network,ec2,dns,iam,s3-backend}/
│   │   ├── backend.tf                  S3 + DynamoDB lock
│   │   └── README.md
│   ├── cloud-init/
│   │   └── ec2-bootstrap.yaml          docker, fail2ban, ufw, swap, user, ssh hardening
│   ├── observability/
│   │   ├── prometheus/prometheus.yml
│   │   ├── grafana/provisioning/{datasources,dashboards}/
│   │   └── exporters/                  postgres-exporter, cadvisor configs
│   ├── jenkins/                        (only if self-hosting Jenkins)
│   │   ├── Dockerfile
│   │   └── pipelines/{ci,deploy-staging,deploy-prod}.Jenkinsfile
│   └── scripts/
│       ├── backup-postgres.sh          cron'd; pg_dump → S3
│       ├── restore-postgres.sh
│       └── deploy.sh                   ssh + compose pull + up
├── .github/workflows/             ci.yml, gitleaks.yml, deploy-staging.yml, deploy-prod.yml
├── .pre-commit-config.yaml        ruff, black, mypy, eslint, prettier, gitleaks, hadolint
├── sonar-project.properties
├── .env.local.example
├── .env.staging.example
├── .env.production.example
├── CLAUDE.md
├── README.md
└── .gitignore
```

## 5. Architecture rules — DO

- Layered: `routers → services → repositories → models`. Routers never query
  the DB; repositories never call vendors; services never construct HTTP
  responses.
- All vendor calls go through `app/adapters/<vendor>/` implementing a
  `Protocol`. Provide a `Mock<Vendor>Adapter` that simulates real timings and
  failure modes.
- **Money**: `Decimal` end-to-end. DB column `NUMERIC(20, 4)`. Never `float`.
  Currency stored as ISO 4217 string alongside the amount.
- **IDs**: UUIDv6 for all primary keys (`uuid6` package). Sortable, no
  enumeration.
- **Idempotency**: every state-changing endpoint accepts an `Idempotency-Key`
  header. Store key + response hash in Redis (24h TTL). Required on
  `POST /investments`.
- **Audit log**: every KYC attempt, accreditation event, bank link attempt,
  investment, and login is written **in the same DB transaction** as the
  action. Never best-effort, never fire-and-forget.
- **All inputs validated** with Pydantic schemas (`extra="forbid"`). Reject
  unknown fields.
- **Parameterized queries only**. Raw SQL is forbidden outside Alembic
  migrations.
- **Migrations** are committed for every schema change. Every environment
  (local, staging, prod) runs `alembic upgrade head` at container start —
  same migrations, no env-specific schema drift.
- **Errors**: define a domain exception hierarchy in `app/core/errors.py`.
  Services raise domain errors; a single global handler maps them to the
  response envelope. Never return raw exception text.
- **Logs are JSON**, structured, with `request_id`, `user_id` (when
  authenticated), `route`, `latency_ms`, `status`. Use `structlog`.
- **Rate limit** auth endpoints (per-IP and per-email) and `POST /investments`
  (per-user) using a Redis sliding window.

## 6. Architecture rules — DON'T

- Don't add abstractions until the second use case appears.
- Don't catch and swallow exceptions. Map at the service boundary; let the
  global handler shape the response.
- Don't put business logic in routers, ORM models, or React components.
- Don't store secrets in code, comments, fixtures, or commit messages.
- Don't use `Any` in Python signatures or `any` in TypeScript.
- Don't log raw PII. Mask emails (`u***@d***.com`), phones (last 4),
  bank account numbers (last 4), JWTs, passwords, full SSNs/PANs.
- Don't bypass the response envelope, even on health checks (return
  `{ "success": true, "data": { "status": "ok" } }`).

## 7. Response envelope (always)

**Success**:
```json
{
  "success": true,
  "data": { "...": "..." },
  "request_id": "01HXXX..."
}
```

**Failure**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The provided input data is invalid."
  },
  "details": {
    "email": ["This field is required."],
    "password": ["Must be at least 8 characters."]
  },
  "request_id": "01HXXX..."
}
```

Rules:
- `success` is always boolean.
- On failure, `error.code` is a stable SCREAMING_SNAKE_CASE string. Frontends
  switch on `code`, not on HTTP status alone.
- `details` is optional; present for validation errors and any error that
  carries field-level info. Always an object whose values are arrays of
  strings (one or more messages per field).
- `request_id` is always present (UUIDv6 from middleware). It is also echoed
  in the `X-Request-ID` response header and in every log line for that
  request.

### Stable error codes (extend as needed)

`VALIDATION_ERROR`, `AUTH_INVALID_CREDENTIALS`, `AUTH_TOKEN_EXPIRED`,
`AUTH_TOKEN_INVALID`, `AUTH_REFRESH_REQUIRED`, `FORBIDDEN`, `NOT_FOUND`,
`CONFLICT`, `RATE_LIMITED`, `IDEMPOTENCY_KEY_REUSED`,
`KYC_NOT_STARTED`, `KYC_PENDING`, `KYC_FAILED`, `KYC_RETRY_EXHAUSTED`,
`ACCREDITATION_PENDING`, `ACCREDITATION_FAILED`,
`BANK_LINK_FAILED`, `BANK_NOT_LINKED`,
`INSUFFICIENT_BALANCE`, `INVESTMENT_FAILED`,
`INTERNAL_ERROR`.

### HTTP status mapping

| Code family             | HTTP |
|-------------------------|------|
| `VALIDATION_ERROR`      | 422  |
| `AUTH_*`                | 401  |
| `FORBIDDEN`             | 403  |
| `NOT_FOUND`             | 404  |
| `CONFLICT`, `IDEMPOTENCY_KEY_REUSED` | 409 |
| `RATE_LIMITED`          | 429  |
| `*_PENDING`             | 202  |
| `*_FAILED`, `INTERNAL_ERROR` | 500/400 (domain decides) |

## 8. Authentication

- Algorithm: HS256 (single instance) or RS256 (multi-instance, prefer when
  scaling). Default: HS256 for this assignment.
- Access token: 15-minute lifetime, payload `{ sub, jti, iat, exp, type:"access" }`.
- Refresh token: 14-day lifetime, rotated on every use, stored hashed
  (sha256) in `refresh_tokens` table. Reuse of a rotated token revokes the
  whole family (refresh-token reuse detection).
- Both delivered as **httpOnly cookies in every environment** (local
  included). In `local`, `Secure=false, SameSite=Lax`. In `staging`/`prod`,
  `Secure=true, SameSite=Strict`.
- Passwords hashed with **argon2id** (`argon2-cffi`), parameters in config.
- Logout revokes the current refresh family.

**Login failures return a single vague code** — `AUTH_INVALID_CREDENTIALS`
("Invalid email or password.") — for both unknown-email and wrong-password
cases, by design. Distinguishing the two would let an attacker probe
registration state from the login form, exposing which HNW emails are
Vestrs clients. Standard practice for finance (Stripe, Coinbase, Schwab).
The audit log records the specific reason internally so support can still
diagnose. Constant-ish work on miss (verify against a sentinel argon2 hash)
keeps response-time leaks closed too.

**Frontend never echoes raw `error.message` or `request_id` to users.**
All toast / inline copy goes through `apps/web/src/lib/error-messages.ts`,
which maps stable `error.code` values to user-friendly strings. The
`request_id` is logged to the browser console for support correlation
only.

## 9. Audit log schema

Table `audit_logs`:

| Column       | Type             | Notes                                  |
|--------------|------------------|----------------------------------------|
| id           | UUIDv6 PK        |                                        |
| timestamp    | TIMESTAMPTZ      | default `now()`                        |
| user_id      | UUIDv6 FK NULL   | null for pre-auth events               |
| action       | TEXT             | e.g. `KYC_SUBMIT`, `INVESTMENT_CREATE` |
| resource_type| TEXT NULL        | e.g. `investment`, `bank_account`      |
| resource_id  | UUIDv6 NULL      |                                        |
| status       | TEXT             | `success`, `failure`, `pending`        |
| request_id   | UUIDv6           |                                        |
| ip           | INET NULL        |                                        |
| user_agent   | TEXT NULL        |                                        |
| metadata     | JSONB NOT NULL   | small, PII-free                        |

Indexes: `(user_id, timestamp DESC)`, `(action, timestamp DESC)`,
`(request_id)`.

## 10. Logging

- `structlog` configured in `app.core.logging`.
- One processor chain for all environments; output is always JSON.
- Required fields per line: `ts`, `level`, `msg`, `request_id`, `route`,
  `method`, `status`, `latency_ms`, `user_id` (nullable), `event`.
- A request-ID middleware generates UUIDv6, attaches to context, echoes in
  `X-Request-ID` response header.
- Uvicorn access log disabled; we emit our own structured access log.
- No secrets, tokens, or unmasked PII in any log line. Pydantic models with
  sensitive fields use `SecretStr` and `repr=False`.

## 11. Testing

- **Unit** (`tests/unit/`): pure service tests with fake repositories +
  fake adapters. No DB, no Redis.
- **Integration** (`tests/integration/`): spin up Postgres + Redis via
  `pytest-docker` or testcontainers; run real Alembic migrations against a
  throwaway schema; exercise routes via `httpx.AsyncClient`.
- **Adapter contract** (`tests/contract/`): each mock adapter must satisfy
  the Protocol; tests assert response shapes and error mapping. When real
  vendors are wired later, the same contract suite runs against recorded
  fixtures.
- **Frontend**: Vitest for components/hooks; one Playwright happy-path
  (signup → KYC pass → accreditation pending→success → bank link → invest).
- Coverage gate: 85% on services, 70% overall.
- Every PR runs the full suite in CI.

## 12. Commands

Backend (from `apps/api/`):
- `uv sync` — install deps
- `uv run uvicorn app.main:app --reload` — dev server
- `uv run alembic revision --autogenerate -m "msg"` — new migration
- `uv run alembic upgrade head` — apply migrations
- `uv run pytest -q` — tests
- `uv run ruff check . && uv run mypy app && uv run black --check .`

Frontend (from `apps/web/`):
- `pnpm install`
- `pnpm dev`
- `pnpm test` / `pnpm test:e2e`
- `pnpm lint && pnpm typecheck`

Stack:
- `docker compose -f infra/compose/docker-compose.yml up --build`
- `docker compose -f infra/compose/docker-compose.staging.yml up -d`

Infra:
- `terraform -chdir=infra/terraform/envs/prod init`
- `terraform -chdir=infra/terraform/envs/prod plan`
- `terraform -chdir=infra/terraform/envs/prod apply`
- `bash infra/scripts/deploy.sh staging` / `... prod`

Quality:
- `make hooks-install` — installs pre-commit framework + git hooks (one-time)
- `make hooks-run` — runs all hooks across the repo
- `make gitleaks` — secret scan (host binary or docker fallback)
- `trivy image vestrs-api:local` (lands in CI at slice 13)

## 17. Frontend design bar (ultra-premium investor product)

The audience is **HNW/UHNW investors**. The frontend must look and feel
like a private-banking / family-office product, not generic SaaS.

**Visual identity**
- Restrained luxury: deep neutrals (off-black, ivory, slate), a single
  accent (gold/champagne or deep emerald). Generous whitespace. No bright
  primary blue, no neon gradients, no glassmorphism.
- Typography: serif for display (Fraunces / Playfair Display), grotesk
  for UI (Inter / Geist). Strong type scale, generous line-height.
- Iconography: thin-stroke (1.5px), one consistent set (Lucide / Phosphor).
- No emojis in product UI.

**Theming**
- Light + dark + system, switchable from a top-bar toggle and persisted.
  Dark is the default ("after-hours" feel).
- All colors via CSS variables that Tailwind reads — no per-component dark
  classes; themed from one place.
- WCAG AA on every text/background pair; AAA on body copy where possible.

**Motion**
- 150–250ms, subtle, purposeful. Respect `prefers-reduced-motion`.
- Page transitions: fade + 4px translate. Step transitions: slide.
- `framer-motion` for orchestrated transitions, CSS for hover/focus.

**UX rules**
- Mobile-first; usable at 360px width.
- Onboarding is a stepper with progress, back navigation, per-step saved
  state.
- Every async action has three states: loading (skeleton, not page
  spinner), success (concise confirm), failure (`error.code` → human copy
  + retry CTA + `Request ID: …` line for support).
- Forms: 44px minimum tap targets, labels above inputs, validation on blur
  (not keystroke), inline error messages adjacent to the field.
- Keyboard: full nav, visible focus rings, ESC closes modals, TAB order
  matches reading order.
- Test with VoiceOver before shipping a slice.

**Components**
- shadcn/ui primitives only. Never raw HTML inputs/buttons.
- Sonner for toasts (top-right desktop, bottom mobile).
- Never expose internal error details. Render `error.message` from the
  envelope.

**Performance**
- LCP < 1.5s on 4G, INP < 200ms.
- Per-route code-split, dynamic-import heavy bits.
- `pnpm lint` and `pnpm typecheck` clean on every PR.
- One Playwright happy-path per visible flow minimum.

**Forbidden**
- Generic Bootstrap / Material look. Centered card on colored background.
- "Powered by …" footers. Auto-playing animations. Stock fintech imagery.

## 18. Git identity (personal account on a multi-account Mac)

This repo belongs to the **personal** GitHub account `lamba-manish`. The
machine also hosts a work account; identities are kept apart by:

- `~/.gitconfig` `includeIf "gitdir:/Users/manishTL/debian-ec2/vestrs/"` →
  `~/.gitconfig-personal`.
- SSH host alias `github.com-personal` in `~/.ssh/config` (the remote URL
  is `git@github.com-personal:lamba-manish/vestrs.git`).

**Author email rule:** the personal gmail address is marked private on
GitHub, so pushing a commit authored with it is rejected with `GH007`.
Commits in this repo **must** be authored with the noreply form:
`43702786+lamba-manish@users.noreply.github.com`. This is set as the
local repo `user.email` (`.git/config`) so it overrides any global
`[user]` block. `~/.gitconfig-personal` should be updated at the user's
discretion to use the same noreply email so other personal repos behave
consistently.

Before any push, verify:

```bash
git config user.email   # must end in @users.noreply.github.com
git remote -v           # must use github.com-personal alias
```

Never use `git config --global` or edit `~/.gitconfig*` from this
project's tasks.

## 19. Branch model + push cadence

Branches:

| Branch                    | Purpose                                                  |
|---------------------------|----------------------------------------------------------|
| `main`                    | Protected. Never deployed directly. Squash-merge target. |
| `slice/<NN>-<short-name>` | Feature branches, one per slice. Source for PRs.         |
| `release/staging`         | Auto-deploys to staging on push (CI deploy job).         |
| `release/production`      | Auto-deploys to production on push, with manual approval.|

Tags: `vMAJOR.MINOR.PATCH` cut on a `release/staging` SHA after smoke tests
pass; tag push promotes that SHA to `release/production`.

Per-slice flow:

1. `git switch -c slice/<NN>-<name>` from latest `main`.
2. Build + verify the slice locally; commit at green milestones (multiple
   commits OK).
3. After my "verified" report, push the branch:
   `git push -u origin slice/<NN>-<name>`. The pre-push hook runs
   `pytest`; failure aborts the push.
4. Open a PR into `main` (`gh pr create`). PR body includes: what changed,
   how to verify, follow-ups.
5. CI (slice 13+) runs lint + types + tests + security scans. Slices 2–12
   rely on local hooks + reviewer.
6. Squash-merge to `main` with the conventional-commit title.
7. To deploy: `git push origin main:release/staging`. To promote:
   tag the verified staging SHA and push the tag; CI fast-forwards
   `release/production` to that tag and runs the prod deploy job behind
   a manual approval gate.

Rules:
- No `--no-verify`, no `--force-with-lease` to `main`/`release/*`, no
  amending merged commits.
- Direct commits to `main` and `release/*` are blocked locally
  (`no-commit-to-branch`).
- Every PR to `main` carries one slice. Cross-cutting refactors get
  their own slice + their own PR.
- **Never delete slice branches** locally or on the remote — neither
  before nor after merge. They are the permanent record of how the
  project was built and the natural anchor for `git blame` /
  archaeology. Renaming or force-pushing them is also forbidden once
  they have been pushed.
- After a slice PR is squash-merged, push and verify state on
  `release/staging`, then promote a tagged SHA to `release/production`.
  The slice branch stays put.

**Server-side branch protection is ON** as of slice 13. The repo was
flipped to **public** in slice 13 to unlock free Actions minutes,
classic branch-protection rules, and SonarCloud's free tier. The
following ruleset is enforced on `main`, `release/staging`, and
`release/production`:

- Required status checks (must pass before merge): every job in
  `ci.yml`, `e2e.yml`, `security.yml`, and `sonarcloud.yml`.
- ≥1 approving review on PRs into `main`.
- No direct pushes (PR-only).
- No force-push, no branch deletion.
- Linear history required (squash-merge only).

Pre-commit hooks remain in place as the first line of defence; CI is
the second.

## 13. Quality gates (must all pass before merge)

Local (pre-commit):
- `ruff` (lint) + `black --check` (format) + `mypy` (types) on changed Python.
- `eslint` + `prettier --check` + `tsc --noEmit` on changed TS/TSX.
- `gitleaks protect --staged` to block secrets in commits.
- `hadolint` on changed Dockerfiles.
- Conventional commit message check.

CI (GitHub Actions, on every PR — workflows under `.github/workflows/`):

`ci.yml`:
1. `api-lint-types`  — `ruff` + `black --check` + `mypy`.
2. `api-tests`       — `pytest` + coverage (Postgres + Redis service containers).
3. `web-lint-types`  — `eslint` + `tsc -b`.
4. `web-tests`       — `vitest`.
5. `web-build`       — `vite build`, dist uploaded as artifact.
6. `build-images`    — `docker build` of api + web (no push).

`e2e.yml`:
7. `playwright`      — happy-path + kyc-failure specs against the full
   stack, run inside `mcr.microsoft.com/playwright:vX.Y.Z-noble` with
   Postgres + Redis service containers. Traces, videos, and HTML
   report uploaded as artifacts on failure.

`security.yml`:
8. `gitleaks`        — full-history secret scan.
9. `trivy`           — HIGH+CRITICAL vuln scan on built images, with
   `.trivyignore` allowlist (every entry justified, ≤60-day re-check
   date). SARIF uploaded to GitHub code scanning. Re-runs weekly.

`sonarcloud.yml`:
10. `sonar`          — coverage + quality-gate decoration on PRs
    (skipped on forks and when `vars.SONAR_ENABLED != 'true'`; needs
    `SONAR_TOKEN` repo secret + `SONAR_ENABLED=true` repo variable).

`release.yml` (slice 14A — fires on push to `release/staging` /
`release/production`):
11. `build-and-push` — build api + web images, **re-run Trivy** on
    the freshly built api image as the final pre-publish gate, then
    push to GHCR with three tags each: full SHA, `sha-<7char>`, and
    the floating `:staging` / `:production` tag. Workers reuse the
    api image with a different entrypoint at compose-time, so we
    publish only `vestrs-api` and `vestrs-web`.

Merge to `main` is blocked unless all required jobs are green AND at
least one human reviewer has approved. Required status checks on
`main` as of slice 13: the 10 jobs in `ci.yml` / `e2e.yml` /
`security.yml` (sonarcloud is held out until first green run is
observed).

## 14. Infrastructure & deploy

- Terraform-managed: VPC + public subnet, EC2 (Ubuntu 24.04, **t3.small**),
  Elastic IP, Security Group (**only 80/tcp + 443/tcp from `0.0.0.0/0`** —
  no public SSH at all), Route53 hosted zone for `manishlamba.com` with
  A records `vestrs`, `staging.vestrs`, `api.vestrs`, `staging-api.vestrs`
  all pointing at the EC2 EIP, IAM role for the box (S3 backup, SSM
  Session Manager, CloudWatch agent), S3 bucket for `pg_dump` backups
  (versioned, SSE-S3, lifecycle: 30 days → glacier).
- Remote state: S3 + DynamoDB lock. State bucket has versioning + SSE.
- Cloud-init bootstrap installs docker, docker-compose plugin, fail2ban
  (with custom jails for `caddy` 401/403/429 spam and `sshd` even though
  ssh isn't public — defence-in-depth), ufw (**deny incoming by default**,
  allow only 80/443; ssh is **not opened**), unattended-upgrades, creates
  a 2GB swapfile (the box only has 2GB RAM), creates a non-root `deploy`
  user, disables `sshd` password auth and root login. Operator access is
  via **AWS SSM Session Manager only** (no public SSH, no key on the box,
  no port 22 in the security group). Audit trail is captured by SSM
  session logging to CloudWatch.
- Deployment is **pull-based**: `infra/scripts/deploy.sh <env>` runs
  on the target host, `docker compose pull`, `docker compose up -d
  --wait`, smoke-tests `https://<api-host>/healthz`. Slice 14B will
  add the SSM-triggered remote runner that calls this script from
  GitHub Actions on a tag promotion.
- Images come from **GHCR**: `ghcr.io/lamba-manish/vestrs-{api,web}`
  with floating `:staging` / `:production` tags plus per-SHA
  immutable tags for rollback (`VESTRS_TAG=sha-abc1234 deploy.sh
  production`). The api image is reused as the worker (compose
  overrides the entrypoint to `arq`).
- **Alembic runs at API container startup in every environment** (entrypoint
  script). No env-specific schemas, no manual migration steps.
- Nightly `pg_dump` to S3 from a cron container; weekly restore drill into
  a scratch DB to prove backups work.
- Secrets: never in git. `.env.<env>` files are populated from AWS SSM
  Parameter Store (`/vestrs/<env>/...`) at deploy time (script fetches →
  writes file → chmod 600). Parameter Store entries are `SecureString`,
  KMS-encrypted with a customer-managed key.

### Edge protection (DDoS / brute force)

- Caddy serves both the static FE bundle (`vestrs.*`, `staging.vestrs.*`)
  and reverse-proxies the API (`api.vestrs.*`, `staging-api.vestrs.*`).
- Caddy enforces a global rate limit (per-IP, sliding window) on `/auth/*`
  and `POST /investments` via the `caddy-ratelimit` module. Static FE hosts
  get a more generous global limit to absorb normal browsing.
- AWS Security Group only exposes 80/443 — ssh is closed entirely, so
  ssh brute-force is structurally impossible.
- fail2ban tails Caddy access logs and adds offending IPs to a `nftables`
  ipset for 15 minutes after N suspicious responses (401/403/429) and a
  separate longer ban for repeated 404 sweeps.
- AWS Shield Standard is on by default (no cost). For burst protection
  beyond t3.small capacity, document a one-line switch to put CloudFront
  + AWS WAF in front (deferred — adds cost).
- All static FE responses get strict CSP, HSTS (preload-eligible),
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and
  `Referrer-Policy: strict-origin-when-cross-origin` injected by Caddy.

## 15. Observability (delivered in slice 14C)

- API exposes `/metrics` via `prometheus-fastapi-instrumentator`.
  `/metrics` and `/healthz` are excluded from the latency histogram so
  the per-route panels reflect real user traffic.
- Local-dev compose profile **`observability`** (opt-in via `make obs-up`)
  brings up Prometheus + Grafana + 5 exporters (node, cadvisor,
  postgres, redis, blackbox) on the same compose network. Two
  dashboards auto-provision: **Vestrs · API** + **Vestrs · Host**.
- Production (default, slice 23): a self-hosted **Prometheus + Grafana**
  pair runs on the EC2 box. Prometheus scrapes the same exporters
  (`api`, `node-exporter`, `cadvisor`, `postgres-exporter`,
  `redis-exporter`, `blackbox-exporter`), 15-day retention, capped
  at 384 MB RAM and 2 GB on-disk. Grafana auto-provisions the
  `Vestrs · API` and `Vestrs · Host` dashboards, anonymous and signup
  off, capped at 256 MB. Caddy fronts it at
  `https://monitoring.vestrs.manishlamba.com` with HSTS + security
  headers. Admin credentials come from SSM Parameter Store
  (`/vestrs/production/GRAFANA_ADMIN_PASSWORD`) via the deploy-time
  `.env.production` render.
- Production (alternative): a single **grafana-agent** container
  scrapes the same exporters and `remote_write`s to **Grafana Cloud
  Mimir** + ships container logs to **Grafana Cloud Loki**. The agent
  only starts when `COMPOSE_PROFILES=cloud-obs` and the
  `GRAFANA_CLOUD_*` env vars are populated; otherwise it's out of
  the compose graph. The two production options are mutually
  exclusive — either run on-box or ship to Cloud, never both, since
  duplicating the scrape doubles the metrics cardinality without
  adding signal.
- Alert rules in `infra/observability/grafana/alerts/vestrs-rules.yml`
  load into Prometheus directly; Grafana Cloud Mimir picks them up via
  `mimirtool rules sync` (slice 14D will wire that into CI). Coverage:
  API 5xx > 5% / 5m, p95 > 1s / 10m, instance down 2m, synthetic
  /healthz failing 5m, host MEM > 90% / 10m, disk > 80% / 10m,
  Postgres connections > 80%, TLS cert < 14d.
- Logs are JSON to stdout; docker's logging driver hands them to
  journald; the agent's Loki source reads them via the Docker socket
  and forwards to Cloud Loki.
- The on-box stack is the **default** observability process.
  Switching to the cloud agent (when free Grafana Cloud quota is
  available) is a one-line `COMPOSE_PROFILES=cloud-obs` flip plus
  filling in the `GRAFANA_CLOUD_*` env vars.
- **Logs**: Loki + Promtail run on-box (slice 24). Promtail tails the
  docker socket and ships every container's stdout/stderr to Loki,
  labelled `stack`/`service`/`container`/`stream`. 7-day retention,
  filesystem-backed. Available as the `Loki` datasource in Grafana
  with UID `vestrs-loki`.
- **Alerting**: Alertmanager runs on-box (slice 25), receives alerts
  from Prometheus via `static_configs`, routes to a single Gmail
  receiver (`manishlamba002@gmail.com`). SMTP creds come from SSM
  (`/vestrs/production/ALERTMANAGER_SMTP_PASSWORD` — must be a Google
  App Password, not the account password). One canary rule
  `AlertingPipelineSmokeTest` fires constantly so the pipeline can be
  verified end-to-end on first deploy; delete it once confirmed.

## 16. Operating principles

- Build one vertical slice end-to-end before starting the next.
- Every milestone ends green: lint + typecheck + tests pass.
- Commit at every green milestone with a conventional-commit message.
- When something deviates from this file, **update this file in the same
  PR**.
