# Deployment

End-to-end pipeline from `git push` to a healthy production container.
This is the operator runbook; for the *why*, see
[ARCHITECTURE.md](./ARCHITECTURE.md) and [SECURITY.md](./SECURITY.md).

## CI/CD chain

| Stage | Trigger | Surface |
|---|---|---|
| **CI** | PR / push to `main` | `ci.yml` — lint, types, tests, image build |
| **E2E** | PR / push to `main` | `e2e.yml` — Playwright happy-path + KYC failure |
| **Security** | PR / push to `main` | `security.yml` — gitleaks (full history) + Trivy |
| **SonarCloud** | PR / push to `main` | `sonarcloud.yml` — coverage + quality gate (≥80% new-code) |
| **Release** | push to `release/production` | `release.yml` — re-Trivy, push images to GHCR |
| **Deploy · production** | Release `success` or push to `release/production` | `deploy-production.yml` — manual-approval SSM RunCommand |

## Required gates before production

1. ≥1 approving review on the PR into `main`
2. All 13 status checks green
3. Linear history (squash-merge only)
4. Fast-forward push from `main` to `release/production` (no PR, no merge commit)
5. `Release` workflow re-Trivy of freshly built images
6. **Manual approval** at the `production` GitHub Environment (slice 27)
7. SSM `SendCommand` against the tag-scoped EC2 instance (slice 25)
8. `bash deploy.sh production` runs only with the GHA-injected `VESTRS_DEPLOY_TOKEN` (slice 30)

## Promote main → production

```bash
# from your local clone, on a clean main:
git switch main
git pull --ff-only
git push origin main:release/production
```

That triggers the Release + Deploy workflows. The Deploy run pauses at
the production-environment gate; click **Review pending deployments →
Approve and deploy** in the Actions UI.

## Rollback

GHCR images are tagged with the immutable full SHA in addition to the
floating `:production` tag.

```bash
# from the production box (Session-Manager shell):
sudo -u deploy bash -c 'cd /opt/vestrs \
  && VESTRS_TAG=sha-abcd123 VESTRS_ALLOW_LOCAL_PROD_DEPLOY=1 \
     bash infra/scripts/deploy.sh production'
```

The override is logged. For non-emergency rollbacks, prefer reverting
the offending commit on `main` and re-promoting through the gated
chain.

## Image promotion

```
slice → main      (PR + 13 checks + 1 review)
main  → release/production    (operator FF push)
GHCR  : ghcr.io/lamba-manish/vestrs-api:production       ← floating
        ghcr.io/lamba-manish/vestrs-api:sha-abc1234       ← immutable, rollback-safe
        ghcr.io/lamba-manish/vestrs-api:abc1234fullsha    ← immutable
```

Worker reuses the api image with a different entrypoint at compose
time (`arq app.workers.WorkerSettings`).

## Smoke tests

The deploy job calls `https://api.vestrs.manishlamba.com/healthz` after
`compose up --wait` and fails if it doesn't return 200 within 100s.
The endpoint is a real **readiness probe** (slice 27) that runs
`SELECT 1` against Postgres and `PING` against Redis on every call.

Manual verification post-deploy:

```bash
curl -sw '\n%{http_code}\n' https://api.vestrs.manishlamba.com/healthz | jq
# expect: 200, data.checks.database.ok = true, data.checks.redis.ok = true

curl -I https://vestrs.manishlamba.com    # → 200
curl -I https://monitoring.vestrs.manishlamba.com   # → 302 to /login (Grafana)
```

## What broke once and how we fixed it

The current pipeline shape was hardened by hitting and fixing each of
these in sequence:

| Issue | Slice | Fix |
|---|---|---|
| GHA SSM role pinned to a destroyed EC2 instance | 25 | Switched to `aws:ResourceTag/Env=production` condition |
| SSM AWS-RunShellScript ran under `dash`; `set -o pipefail` failed | 30 | Wrapped script body in `bash -euo pipefail -c "..."` |
| `/opt/vestrs/.git` owned by root (operator-as-root drift) | 30 | Defensive `chown -R deploy:deploy /opt/vestrs` in the SSM script |
| `docker inspect --format '{{.Image}}'` template error killed deploy on success | 30 | Replaced with `docker compose images` |
| Direct `bash deploy.sh production` from Session-Manager shell skipped every gate | 30 | `VESTRS_DEPLOY_TOKEN` guard + audited `VESTRS_ALLOW_LOCAL_PROD_DEPLOY` override |
| `AWS_INSTANCE_ID_PRODUCTION` repo variable went stale on EC2 rebuild | 30 (operator) | Refreshed; medium-term: replace static var with tag-based lookup at deploy time (see ROADMAP.md) |

## Production observability links

- Grafana: <https://monitoring.vestrs.manishlamba.com>
  - Dashboards: **Vestrs · API**, **Vestrs · Host**, **Vestrs · Containers**
  - Datasources: Prometheus + Loki (both on-box)
- Logs: Grafana → Explore → datasource Loki → `{service="api"}` for backend, `{stack="vestrs-production"}` for everything
- Alerts: routed via Alertmanager → Gmail SMTP (slice 25)
