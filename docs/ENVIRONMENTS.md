# Environments

Three environments selected by `APP_ENV`. The same compose graph + same
migrations run in each — only the values change.

| | `local` | `staging` | `production` |
|---|---|---|---|
| URL (web) | `http://localhost:3000` | `https://staging.vestrs.manishlamba.com` | `https://vestrs.manishlamba.com` |
| URL (api) | `http://localhost:8000` | `https://staging-api.vestrs.manishlamba.com` | `https://api.vestrs.manishlamba.com` |
| URL (monitoring) | `make obs-up` (opt-in) | n/a | `https://monitoring.vestrs.manishlamba.com` |
| TLS | none | Caddy + Let's Encrypt | Caddy + Let's Encrypt |
| Cookies | `Secure=0`, `SameSite=Lax` | `Secure=1`, `SameSite=Strict` | `Secure=1`, `SameSite=Strict` |
| Mocked vendors | yes | yes | yes (assignment scope) |
| Logs | `debug`, pretty | `info`, JSON | `info`, JSON |
| `/metrics` | on | on | on |
| Loki retention | n/a (logs to stdout) | n/a | 7 days on-box |
| Backups | n/a | nightly `pg_dump` → S3 | nightly `pg_dump` → S3, 30d → Glacier |

## Stages from commit to production

```
1.  developer pushes a slice branch
        │
        ▼
2.  Pull request opened against `main`
        │   13 required status checks:
        │   - api: ruff + black + mypy
        │   - api: pytest (postgres + redis service containers)
        │   - web: eslint + tsc + vitest + vite build
        │   - docker: build api, worker, web images
        │   - playwright: happy-path + kyc-failure
        │   - security: gitleaks (full history) + trivy (api+web)
        │   - sonarcloud: code analysis + quality gate (≥80% new-code coverage)
        ▼
3.  ≥1 approving review + all checks green ⇒ squash-merge to `main`
        │
        ▼
4.  Operator promotes: `git push origin main:release/production`
        │   (fast-forward only — branch protection blocks force-push + delete)
        ▼
5.  `Release` workflow on `release/production`
        │   - re-runs Trivy on the freshly built images
        │   - pushes ghcr.io/lamba-manish/vestrs-{api,web} with three tags:
        │     full SHA, `sha-<7char>`, and floating `:production`
        ▼
6.  `Deploy · production` workflow
        │   - assumes the `vestrs-production-gha-deploy` IAM role via OIDC
        │   - PAUSES at the `production` GitHub Environment for human approval
        │     (only `lamba-manish` is configured as approver)
        ▼
7.  Operator clicks "Approve and deploy"
        │
        ▼
8.  SSM `SendCommand` against the EC2 instance
        │   - tag-scoped policy (slice 25): aws:ResourceTag/Env=production
        │     so EC2 rebuilds don't drift the role policy
        │   - command runs `bash -euo pipefail -c "..."` (slice 30)
        │   - chowns /opt/vestrs to deploy:deploy (slice 30)
        │   - injects VESTRS_DEPLOY_TOKEN so deploy.sh's prod guard accepts the call
        ▼
9.  `deploy.sh production` on the box
        │   - docker login ghcr.io
        │   - compose pull + compose up -d --wait
        │   - alembic upgrade head runs at API container startup
        │   - smoke-test https://api.vestrs.manishlamba.com/healthz
        ▼
10. Healthy → Deploy job completes green
```

## Production-deploy lockdown (slice 30)

Direct invocation of `deploy.sh production` from a Session-Manager
shell now refuses with exit-10 unless the GHA-injected
`VESTRS_DEPLOY_TOKEN` is present. Break-glass override:

```bash
VESTRS_ALLOW_LOCAL_PROD_DEPLOY=1 bash deploy.sh production
```

The override is logged so emergency direct deploys are auditable.

## Configuration sources

| Source | Used for |
|---|---|
| `apps/api/app/core/config.py` | typed `Settings` from env (pydantic-settings) |
| `.env.<env>.example` | tracked template |
| `.env.<env>` | gitignored, populated from SSM Parameter Store at deploy time |
| `/vestrs/<env>/<KEY>` SSM parameters | source of truth, KMS-encrypted |
| `vars.AWS_DEPLOY_ROLE_PRODUCTION` etc. | repo-level GitHub variables |

Never `os.environ[...]` directly. Always `get_settings().*`.
