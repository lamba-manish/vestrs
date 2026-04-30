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

## Observability (slice 14C)

### Locally
```bash
make obs-up      # brings up prometheus + grafana + 5 exporters
# Grafana → http://localhost:3001  (admin / admin)
# Prom    → http://localhost:9090
make obs-down    # stops them; data persists in named volumes
```

Two dashboards auto-provision: **Vestrs · API** (RPS, error rate,
p50/p95/p99 by route, FD count, synthetic uptime) and **Vestrs · Host**
(CPU, MEM, Disk, Net, container RSS, Postgres connections). Alert
rules in `infra/observability/grafana/alerts/vestrs-rules.yml` load
into Prometheus immediately; Grafana Cloud Mimir picks them up via
`mimirtool rules sync` (slice 14D wires that into CI).

### In staging / production

`infra/compose/docker-compose.{staging,prod}.yml` includes the same
exporters plus a `grafana-agent` service that scrapes them and
`remote_write`s metrics + ships container logs to Grafana Cloud.

The agent only starts when explicitly enabled via the `cloud-obs`
compose profile. To turn it on:

1. **Provision a Grafana Cloud free stack** (https://grafana.com →
   *Create stack*). Note the Mimir URL + username and the Loki URL +
   username.
2. **Mint an access policy token** with `metrics:write` + `logs:write`
   scopes on that stack.
3. **Stash the secrets in SSM Parameter Store**:
   ```bash
   ENV=staging
   for k in PROM_URL PROM_USER LOKI_URL LOKI_USER API_KEY; do
     aws ssm put-parameter --type SecureString \
       --name "/vestrs/$ENV/grafana_cloud_$(echo $k | tr A-Z a-z)" \
       --value '<paste>'
   done
   ```
4. **Update `.env.<env>`** (the SSM-stored copy) so cloud-init renders:
   ```
   COMPOSE_PROFILES=cloud-obs
   GRAFANA_CLOUD_PROM_URL=...
   GRAFANA_CLOUD_PROM_USER=...
   GRAFANA_CLOUD_LOKI_URL=...
   GRAFANA_CLOUD_LOKI_USER=...
   GRAFANA_CLOUD_API_KEY=...
   ```
5. `git push <sha>:release/<env>` — next deploy starts the agent.

Without those env vars set, the `grafana-agent` service stays out of
the compose graph entirely (zero overhead).

## Bootstrap from zero (slice 14B)

The whole production stack — VPC, EC2, EIP, Route53 records, IAM
roles, S3 backup bucket, GitHub OIDC trust — is in
`infra/terraform/`. Order matters; do these once per AWS account.

### Prerequisites
- AWS account, AWS CLI v2, terraform ≥1.6 on your laptop.
- `aws configure` (or SSO) with permissions to create IAM, EC2, S3,
  DynamoDB, Route53, SSM resources.
- Existing Route53 hosted zone for your apex domain (the `dns`
  module references it via data source — it doesn't create the zone).

### Step 1 · State backend
```bash
cd infra/terraform/bootstrap
terraform init
terraform apply           # creates vestrs-tfstate (S3) + vestrs-tfstate-lock (DDB) + GitHub OIDC provider
```
Then uncomment the `backend "s3" {}` block in `bootstrap/main.tf` and
run `terraform init -migrate-state` to move bootstrap's own state
into the bucket it just created.

### Step 2 · SSM parameters (per env)
Cloud-init reads these at instance boot. Create them as `SecureString`
ahead of `terraform apply`:

```bash
ENV=staging     # or production
REGION=ap-south-1

# GHCR pull credential — `<gh-username>:<personal-access-token-with-read:packages>`
aws ssm put-parameter --region $REGION --type SecureString \
  --name "/vestrs/$ENV/ghcr_credential" \
  --value 'lamba-manish:ghp_xxx'

# Full .env.<env> file content (the deploy script's contract).
aws ssm put-parameter --region $REGION --type SecureString \
  --name "/vestrs/$ENV/env_file" \
  --value "$(cat .env.$ENV.example | sed 's/__from_ssm__/<real-secret>/g')"
```

### Step 3 · Apply per-env stack
```bash
cd infra/terraform/envs/staging
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Outputs include `instance_id`, `elastic_ip`, and `deploy_role_arn`.
Add the latter as a repo variable so the deploy workflows can use it:

```bash
gh variable set AWS_DEPLOY_ROLE_STAGING --body "<deploy_role_arn>" --repo lamba-manish/vestrs
gh variable set AWS_INSTANCE_ID_STAGING  --body "<instance_id>"   --repo lamba-manish/vestrs
gh variable set AWS_REGION                --body "ap-south-1"      --repo lamba-manish/vestrs
```

(Same pair for `production`, `AWS_DEPLOY_ROLE_PRODUCTION` etc.)

### Step 4 · Configure GitHub Environments
- **Settings → Environments → New environment → `staging`** (no protection rules).
- **Settings → Environments → New environment → `production`**:
  add yourself as a *Required reviewer*. The `deploy-production.yml`
  job pauses there until you click Approve.

### Step 5 · First deploy
- Push the verified `main` SHA to `release/staging`:
  ```bash
  git push origin <sha>:release/staging
  ```
  This fires `release.yml` (publishes images) → `deploy-staging.yml`
  (SSM → `deploy.sh staging` → smoke test).
- Repeat to `release/production` once staging is verified.

### Disaster recovery
- Backups land at `s3://vestrs-<env>-pgbackups/<env>/<utc-iso>.sql.gz`
  nightly via the systemd timer in cloud-init.
- Manual snapshot before risky migrations:
  `bash infra/scripts/backup-postgres.sh <env>`
- Restore (requires confirmation by typing the env name):
  `bash infra/scripts/restore-postgres.sh <env> s3://...`

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
