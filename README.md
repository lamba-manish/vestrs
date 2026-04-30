# Vestrs · Cross-border investment onboarding

A take-home project rebuilt as an end-to-end production system. The
flow is the canonical private-banking sequence: **signup → KYC →
accreditation review → bank link → first investment → audit log**.
Every external vendor is behind an adapter Protocol, every state-changing
action writes a same-transaction audit row, and the whole stack lives
on a single AWS EC2 box behind Caddy + Let's Encrypt.

> **Live**: https://vestrs.manishlamba.com — try a signup; the demo
> mock-vendors resolve in seconds. API health: https://api.vestrs.manishlamba.com/healthz.
> Docs: https://api.vestrs.manishlamba.com/docs.
>
> The site is provisioned for a one-week evaluation window and then
> torn down.

---

## At a glance

| | |
|---|---|
| **Backend** | Python 3.12 · FastAPI (async) · SQLAlchemy 2 async · Alembic · ARQ (Redis worker) · structlog · argon2id · pyjwt |
| **Frontend** | Vite 5 · React 19 · TypeScript strict · Tailwind · shadcn/ui · TanStack Query · framer-motion · Zod |
| **Data** | PostgreSQL 16 (NUMERIC(20,4) money, JSONB metadata, UUIDv6 PKs) · Redis 7 |
| **Edge** | Caddy 2 (HTTP/3, auto-TLS, security headers, SPA fallback) |
| **Cloud** | AWS — EC2 t3.small, Route53, S3 (state + backups), DynamoDB (state lock), SSM (Parameter Store + Session Manager) |
| **CI** | GitHub Actions — ruff/black/mypy · vitest · Playwright · Trivy · gitleaks · SonarCloud · GHCR push |
| **CD** | Push to `release/production` → re-Trivy → publish to GHCR → SSM `RunCommand` → `deploy.sh` on EC2 → smoke `/healthz` |
| **Observability** | `/metrics` (FastAPI) · prometheus + grafana local profile · grafana-agent → Grafana Cloud Mimir+Loki for staging/prod |
| **Quality gates** | 13 required CI checks before merge to `main` · branch protection · pre-commit (16 hooks) · pre-push pytest · CVE allowlist policy |

---

## What's interesting in here

A take-home brief describes a flow; this repo is the **opinionated
production implementation** of that flow. Things worth peeking at:

- **`apps/api/app/adapters/`** — KYC / accreditation / bank are
  vendor-agnostic Protocols. The mocks ship the same surface the real
  Shufti / Jumio / Plaid integrations would. Email-tagged emails
  (`+kyc_fail`, `+acc_fail`, `+kyc_pending`) deterministically drive
  every decision branch from the FE.
- **`apps/api/app/repositories/audit_logs.py`** — every action writes
  an audit row in the same DB transaction as the action itself.
  Failures get an *independent-session* write so they survive the
  domain-error rollback. Cursor-paginated UUIDv6 keys.
- **`apps/api/app/api/v1/investments.py`** — `Idempotency-Key` is
  required, replays return the cached envelope, body-mismatched
  replays return `409 IDEMPOTENCY_KEY_REUSED` and write a
  `INVESTMENT_BLOCKED` audit row.
- **`apps/web/src/lib/api.ts`** + **`apps/web/src/lib/error-messages.ts`**
  — every backend response goes through a Zod-typed envelope; user-
  visible toasts come from a code-keyed map, never `error.message`,
  never `request_id`.
- **`infra/terraform/`** — bootstrap stack (state bucket + DDB lock +
  GH OIDC provider) + per-env stacks composing six modules. Strict
  IAM trust: deploy role's `sub` is pinned to `release/<env>` AND the
  matching GitHub Environment.
- **`infra/cloud-init/ec2-bootstrap.yaml.tpl`** — first-boot user-data:
  docker, ufw (deny-by-default, only 80/443 open), fail2ban (Caddy
  log jail), 2GB swap, sshd hardening, repo clone, SSM-fetched env
  file + GHCR PAT, systemd timer for nightly pg_dump → S3.
- **`.github/workflows/`** — ci, e2e, security, sonarcloud, release,
  deploy-staging, deploy-production. The release pipeline is
  Trivy-gated; the production deploy gates on a GitHub Environment
  with a manual reviewer.

---

## Architecture sketch

```
                       ┌───────────────────┐
       Browser  ───────▶ Caddy (TLS, HSTS) │
                       └─────────┬─────────┘
                                 │
                       ┌─────────┴─────────┐
                       │                   │
              static dist/             reverse_proxy
              (web-publish)              api:8000
                                            │
                                  ┌─────────┴─────────┐
                                  │   FastAPI (uvicorn)│
                                  │  routers→services  │
                                  │   →repositories→   │
                                  │  Postgres / Redis  │
                                  └─┬──────────────┬───┘
                                    │              │
                       enqueue accreditation        │
                                    │              │
                              ┌─────▼─────┐  ┌─────▼─────┐
                              │ ARQ worker│  │  Postgres │
                              │  (resolve)│  │  (audit,  │
                              └───────────┘  │  users …) │
                                             └───────────┘
```

Deeper: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Evaluator quickstart (local)

Requires Docker + Docker Compose v2 + GNU make.

```bash
make bootstrap   # copies *.example env files (idempotent)
make up          # builds and starts api + web + postgres + redis
```

- Web: http://localhost:3000
- API health: http://localhost:8000/healthz
- API docs: http://localhost:8000/docs

The full happy-path takes ~30 seconds:

1. Signup → arbitrary email + ≥12-char password.
2. Profile → name + ISO-2 nationality / country.
3. KYC → click *Submit KYC* (mock returns success).
4. Accreditation → *Submit*; the page polls every 2s, the ARQ worker
   resolves it in ~5s.
5. Bank link → any 9-digit account, 8-digit routing.
6. Invest → an amount under the seeded mock balance.
7. Audit log → every action you just took, with metadata.

Demo controls (email tags) for forcing failure branches:

| Email contains | Outcome |
|---|---|
| `+kyc_fail` | KYC returns FAILED with retry. |
| `+kyc_pending` | KYC stays PENDING (manual resolve). |
| `+acc_fail` | Accreditation eventually FAILS. |
| `+bank_fail` | Bank link rejected. |

Stop with `make down`. Reset volumes with `make clean` (destroys local DB).

---

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — request flow,
  data model, adapter pattern, slice journal, performance budget.
- **[docs/SECURITY.md](docs/SECURITY.md)** — auth model, audit log
  shape, secrets management, security headers, CVE policy.
- **[docs/RUNBOOK.md](docs/RUNBOOK.md)** — bootstrap-from-zero AWS
  deploy, observability bring-up, disaster recovery.
- **[CLAUDE.md](CLAUDE.md)** — project conventions (response envelope,
  env matrix, error codes, branch model). Also the source-of-truth
  document the AI pair-programmer reads at the start of every session.

---

## Branch + release model

| Branch | Purpose |
|---|---|
| `main` | Protected; squash-merge target. 13 required CI checks + 1 review (admin override during solo dev). |
| `slice/<NN>-<name>` | Feature branches; one per slice. PR target is `main`. **Never deleted**, even after merge — they are the build journal. |
| `release/staging` | Push fires `release.yml` (Trivy-gated GHCR publish) → `deploy-staging.yml` (SSM RunCommand). |
| `release/production` | Same pipeline; the deploy job pauses on a required-reviewer GitHub Environment. |

48-slice journal (so far) — see the commit log on `main` and the
matching `slice/*` branches. Highlights:

- 0–10: backend (envelope, middleware, auth, KYC, accreditation, bank, invest, audit).
- 11–12: frontend shell + onboarding flow.
- 13: GitHub Actions / Trivy / Sonar / Playwright / branch protection.
- 14A: GHCR release pipeline + compose overlays + Caddy.
- 14B: Terraform AWS stack + SSM-triggered deploys + nightly pg_dump.
- 14C: `/metrics` endpoint + observability (local Prom/Grafana + Cloud agent).
- 15-17: UX polish (favicon, optimistic top-nav, vendor chunking).
- 18: this submission README + docs.

---

## Tradeoffs and what's deferred

- **Single-AZ EC2.** No HA — picked deliberately for the take-home
  budget. The compose stack runs everything on one t3.small;
  Postgres + Redis are local volumes. Production-grade move would be
  RDS Multi-AZ + ElastiCache + multiple stateless app instances
  behind an ALB.
- **Mock vendors.** Real KYC / accreditation / bank integrations live
  behind the adapter Protocols; the swap-in is a config + new
  `<Vendor>Adapter` class. The brief calls for mocks; the structure
  shows the integration shape.
- **Frontend rate-limit messaging.** Backend returns
  `Retry-After`-bearing 429s; the FE currently surfaces a generic
  "Too many requests" toast without the wait time. (Slice 19 candidate.)
- **Mimir rules sync from CI.** Alert rules live in the repo
  (`infra/observability/grafana/alerts/`) but `mimirtool rules sync`
  is operator-run today; CI hook is a slice 14D follow-up.
- **Worker liveness.** The arq worker has `restart: always` and
  no inherited HEALTHCHECK (slice 16). Crashloop is caught; subtle
  hangs would need an arq-specific Redis heartbeat probe — doable in
  one slice if surfaced later.

---

## Repo layout

```
vestrs/
├── apps/
│   ├── api/              FastAPI + SQLAlchemy + Alembic + ARQ worker
│   └── web/              Vite + React + Tailwind + Playwright
├── infra/
│   ├── terraform/        bootstrap + 6 modules + per-env stacks
│   ├── compose/          local + staging + production overlays
│   ├── caddy/            two Caddyfiles (staging.* / *) with HSTS+CSP
│   ├── cloud-init/       EC2 first-boot user-data template
│   ├── observability/    prometheus, grafana provisioning, agent.river,
│   │                     dashboards (vestrs-api / vestrs-host),
│   │                     alert rules, exporter configs
│   └── scripts/          deploy.sh + backup/restore-postgres.sh
├── docs/                 ARCHITECTURE.md, SECURITY.md, RUNBOOK.md
├── .github/workflows/    ci, e2e, security, sonarcloud, release,
│                         deploy-{staging,production}
├── CLAUDE.md             project conventions / AI working agreement
└── README.md             you are here
```

---

## License + contact

Internal take-home build. Not licensed for redistribution.
Questions: see the issue tracker on the repo.
