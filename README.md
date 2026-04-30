# Vestrs — Mini Investment Onboarding Platform

> Cross-border investment onboarding flow:
> signup → KYC/AML/liveness → accreditation → bank link → investment → audit log.

This README is intentionally short during early slices. It will grow into the
full submission document (architecture, trade-offs, ops runbook) at Slice 21.

For project conventions, response envelope, env matrix, security baseline,
and architecture rules, read [`CLAUDE.md`](./CLAUDE.md).

## Quick start (local)

Requirements: Docker + Docker Compose v2, GNU make.

```bash
make bootstrap   # copies *.example env files (idempotent)
make up          # builds and starts api + web + postgres + redis
make logs        # tail
```

Endpoints:
- API health: `http://localhost:8000/healthz`
- API docs: `http://localhost:8000/docs`
- Web: `http://localhost:3000`

Stop with `make down`. Reset volumes with `make clean` (destroys local DB).

## CI

Four workflows guard `main`:

- **CI** (`ci.yml`) — lint, typecheck, test (BE + FE), build images.
- **E2E** (`e2e.yml`) — Playwright happy-path + KYC-failure specs
  against a full stack inside the official Playwright runner image.
- **Security** (`security.yml`) — gitleaks full-history secret scan +
  Trivy HIGH/CRITICAL image scan, with a justified `.trivyignore`
  allowlist. Re-runs weekly so new CVEs surface even in unchanged
  base images.
- **SonarCloud** (`sonarcloud.yml`) — coverage + quality-gate
  decoration on PRs. Requires the `SONAR_TOKEN` repo secret AND the
  repository variable `SONAR_ENABLED=true`. The job skips cleanly
  while either is missing so PRs aren't blocked during setup.

Reproduce CI locally with `make ci-local` (runs the same lint, types,
tests, and gitleaks gates inside the dev container).

### Running e2e locally

```bash
make up                # bring up the stack
make e2e-install       # one-time: install Chromium inside the web container
make e2e               # run Playwright
```

Reports land at `apps/web/playwright-report/` and traces at
`apps/web/test-results/`.

## Releases

Pushing to `release/staging` or `release/production` triggers
`.github/workflows/release.yml`, which:

1. Builds api + web images.
2. Re-runs Trivy (HIGH+CRITICAL fail) against the freshly built api
   image — same gate as PR CI, repeated at release time so a CVE that
   landed between merge and release blocks the publish.
3. Pushes to GHCR with three tags each:
   - `ghcr.io/lamba-manish/vestrs-{api,web}:<full-sha>` (immutable)
   - `:sha-<7char>` (immutable, short)
   - `:staging` or `:production` (floating; latest publish on that branch)

Promote staging → production by pushing the verified staging SHA to
`release/production`:

```bash
git push origin <verified-sha>:release/production
```

Roll back without retagging:

```bash
VESTRS_TAG=sha-abc1234 bash infra/scripts/deploy.sh production
```

### Deploying

`infra/scripts/deploy.sh <staging|production>` runs **on the target
host** (slice 14A — slice 14B will trigger this remotely from CI via
SSM). It pulls the latest images, runs `docker compose up -d --wait`,
and smoke-tests `https://<api-host>/healthz`. The api container's
entrypoint runs `alembic upgrade head` on every start, so migrations
apply automatically.

The `.env.<env>` file must already be populated from AWS SSM
Parameter Store before invoking `deploy.sh`. The script refuses to
proceed without it.

### Reading a red Trivy job

Trivy fails the build on any HIGH or CRITICAL CVE with a fix
available. Two paths to green:

1. **Bump the base image** — the usual fix. Change the `FROM` line in
   the relevant `Dockerfile`, rebuild, push.
2. **Allowlist with a re-check date** — when no fix exists yet, add
   the CVE to `.trivyignore` with a one-line justification and a
   `Re-check by: YYYY-MM-DD` comment ≤60 days out. The weekly schedule
   will re-fail once a fix lands.

Never blanket-allowlist; always document.
