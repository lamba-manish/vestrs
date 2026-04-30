# Operator runbook

Step-by-step procedures the on-call (you, or future-you) reaches for
under stress. Each section is self-contained.

## CI workflows

Four guard `main`. Required-status-checks gate the merge button.

| Workflow | What it does |
|---|---|
| `ci.yml` | lint/typecheck/test (BE+FE), `vite build`, `docker build` of api+web. |
| `e2e.yml` | Playwright happy-path + KYC-failure inside `mcr.microsoft.com/playwright:v1.49.1-noble` against a compose-up stack. |
| `security.yml` | gitleaks full-history + Trivy on the api image + Trivy filesystem-scan on `apps/web/dist/`. Re-runs weekly. |
| `sonarcloud.yml` | Coverage upload + quality-gate decoration. Gated on `vars.SONAR_ENABLED == 'true'` so PRs aren't blocked while setting up. |
| `release.yml` | On push to `release/*` — re-Trivy → publish to GHCR with SHA + `sha-<7>` + floating env tag. |
| `deploy-{staging,production}.yml` | OIDC into AWS, `ssm:SendCommand` on the matching env's instance, polls until terminal, smoke-tests `/healthz`. Production gates on a GitHub Environment with required reviewer. |

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

### Reading a red Trivy job

Trivy fails the build on any HIGH or CRITICAL CVE with a fix
available. Two paths to green:

1. **Bump the base image** — the usual fix. Change the `FROM` line
   in the relevant `Dockerfile`, rebuild, push.
2. **Allowlist with a re-check date** — when no fix exists yet, add
   the CVE to `.trivyignore` with a one-line justification and a
   `Re-check by: YYYY-MM-DD` comment ≤60 days out. The weekly
   schedule will re-fail once a fix lands.

Never blanket-allowlist; always document.

---

## Releases

Pushing to `release/staging` or `release/production` triggers
`.github/workflows/release.yml`, which:

1. Builds api + web images. The web build receives `VITE_API_URL`
   and `VITE_APP_ENV` as build args (vite inlines them at build
   time, so the deployed FE bundle has the right API URL baked in).
2. Re-runs Trivy (HIGH+CRITICAL fail) on the freshly built api
   image. Catches CVEs that landed between PR merge and release.
3. Pushes to GHCR with three tags each:
   - `ghcr.io/lamba-manish/vestrs-{api,web}:<full-sha>` (immutable)
   - `:sha-<7char>` (immutable, short)
   - `:staging` or `:production` (floating, latest publish)

Promote staging → production by pushing the verified staging SHA:

```bash
git push origin <verified-sha>:release/production
```

Roll back without retagging:

```bash
VESTRS_TAG=sha-abc1234 bash infra/scripts/deploy.sh production
```

### Deploying

`infra/scripts/deploy.sh <staging|production>` runs **on the target
host**. Pulls images, runs `docker compose up -d --wait`,
smoke-tests `https://<api-host>/healthz`. The api container's
entrypoint runs `alembic upgrade head` on every start, so migrations
apply automatically.

The `.env.<env>` file must already be populated from AWS SSM
Parameter Store before invoking `deploy.sh`. The script refuses to
proceed without it.

The CD path (`deploy-{staging,production}.yml`) calls this script
remotely via SSM `RunCommand`.

---

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
terraform apply
# creates vestrs-tfstate (S3) + vestrs-tfstate-lock (DDB) + GitHub OIDC provider
terraform init -migrate-state   # move bootstrap's own state into the bucket
```

### Step 2 · SSM parameters (per env)
Cloud-init reads these at instance boot. Create them as
`SecureString` ahead of `terraform apply`:

```bash
ENV=production     # or staging
REGION=ap-south-1

# GHCR pull credential — `<gh-username>:<personal-access-token-with-read:packages>`
aws ssm put-parameter --region $REGION --type SecureString \
  --name "/vestrs/$ENV/ghcr_credential" \
  --value 'lamba-manish:ghp_xxx'

# Full .env.<env> file content (the deploy script's contract).
# Replace __from_ssm__ markers with real values before piping in.
aws ssm put-parameter --region $REGION --type SecureString \
  --name "/vestrs/$ENV/env_file" \
  --value file://.env.$ENV.real
```

### Step 3 · Apply per-env stack
```bash
cd infra/terraform/envs/production
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Outputs include `instance_id`, `elastic_ip`, and `deploy_role_arn`.

### Step 4 · Wire repo variables
```bash
gh variable set AWS_REGION                  --body "ap-south-1"
gh variable set AWS_INSTANCE_ID_PRODUCTION  --body "<instance_id>"
gh variable set AWS_DEPLOY_ROLE_PRODUCTION  --body "<deploy_role_arn>"
```

### Step 5 · Configure GitHub Environments
- **Settings → Environments → New environment → `staging`** (no
  protection rules).
- **Settings → Environments → New environment → `production`**:
  add yourself as a *Required reviewer*. The
  `deploy-production.yml` job pauses there until you approve.

### Step 6 · First deploy
- `git push origin <sha>:release/production` — fires `release.yml`
  (publishes images) → `deploy-production.yml` (SSM → `deploy.sh
  production` → smoke test).

---

## Observability bring-up

### Locally
```bash
make obs-up      # prometheus + grafana + 5 exporters (compose profile)
# Grafana → http://localhost:3001  (admin / admin)
# Prom    → http://localhost:9090
make obs-down
```

Two dashboards auto-provision: **Vestrs · API** (RPS, error rate,
p50/p95/p99 by route, FD count, synthetic uptime) and
**Vestrs · Host** (CPU/MEM/Disk/Net + container RSS + Postgres
connections). Alert rules in
`infra/observability/grafana/alerts/vestrs-rules.yml` load into
Prometheus immediately.

### In staging / production

`infra/compose/docker-compose.{staging,production}.yml` includes the
exporters + a `grafana-agent` service that scrapes them and
`remote_write`s metrics + ships container logs to Grafana Cloud.

The agent only starts when explicitly enabled via the `cloud-obs`
compose profile. To turn it on:

1. **Provision a Grafana Cloud free stack** (https://grafana.com →
   *Create stack*). Note the Mimir URL + username and the Loki URL +
   username.
2. **Mint an access policy token** with `metrics:write` +
   `logs:write` scopes on that stack.
3. **Stash the secrets in SSM Parameter Store**:
   ```bash
   ENV=production
   for k in PROM_URL PROM_USER LOKI_URL LOKI_USER API_KEY; do
     aws ssm put-parameter --type SecureString \
       --name "/vestrs/$ENV/grafana_cloud_$(echo $k | tr A-Z a-z)" \
       --value '<paste>'
   done
   ```
4. **Update `.env.<env>`** (the SSM-stored copy) so cloud-init
   renders:
   ```
   COMPOSE_PROFILES=cloud-obs
   GRAFANA_CLOUD_PROM_URL=...
   GRAFANA_CLOUD_PROM_USER=...
   GRAFANA_CLOUD_LOKI_URL=...
   GRAFANA_CLOUD_LOKI_USER=...
   GRAFANA_CLOUD_API_KEY=...
   ```
5. `git push <sha>:release/<env>` — next deploy starts the agent.

Without those env vars set, the `grafana-agent` service stays out
of the compose graph entirely (zero overhead).

---

## Operator access (no public SSH)

```bash
brew install --cask session-manager-plugin    # one-time
aws ssm start-session --target <instance-id> --region ap-south-1
sudo -iu deploy                               # become the service user
cd /opt/vestrs
```

You'll land as `ssm-user` and switch to `deploy`. All SSM sessions
are logged to CloudWatch (audit trail).

---

## Disaster recovery

### Backups

Nightly via systemd timer in cloud-init:
`s3://vestrs-<env>-pgbackups-<account-id>/<env>/<utc-iso>.sql.gz`.

Manual snapshot before risky migrations:

```bash
bash infra/scripts/backup-postgres.sh production
# or with --no-s3 to keep it on disk only
```

### Restore

Confirmation by typing the env name guards the `DROP DATABASE`:

```bash
bash infra/scripts/restore-postgres.sh production s3://vestrs-production-pgbackups-…/production/2026-04-30T031700Z.sql.gz
```

The script:

1. `aws s3 cp` the dump to a tmp file.
2. Prompts for the env-name confirmation.
3. `DROP DATABASE` + `CREATE DATABASE` in the live container.
4. `psql -v ON_ERROR_STOP=1` on the dump.
5. `alembic upgrade head` to apply any subsequent migrations
   (idempotent if the dump's schema is current).

### Worker hung jobs

`arq`'s default behaviour is to retry failed jobs with exponential
backoff (3 attempts, 60s/180s/420s). Hung jobs (no progress in 10
min) get killed by the worker's per-job timeout and re-enqueued.

To inspect the queue depth:

```bash
docker exec vestrs-production-redis-1 redis-cli LLEN arq:queue:default
```

To drain everything (last resort):

```bash
docker exec vestrs-production-redis-1 redis-cli DEL arq:queue:default
```

---

## SonarCloud setup (one-time per repo)

1. Sign in at https://sonarcloud.io with the GitHub account that
   owns the repo.
2. **Import organization from GitHub** → pick the org.
   Organization key must be lowercase + hyphens (no underscores).
3. **+ → Analyze new project** → pick the repo. Project key
   auto-derives as `<org>_<repo>` (underscores OK in project key).
4. **Administration → Analysis Method → With GitHub Actions**.
   This **disables Automatic Analysis**, which would conflict with
   the CI scan. (If you skip this step the workflow logs say
   "You are running CI analysis while Automatic Analysis is enabled.")
5. **Mint a token** under My Account → Security.
6. Stash it in the repo:
   ```bash
   gh secret set SONAR_TOKEN --repo lamba-manish/vestrs
   gh variable set SONAR_ENABLED --body "true" --repo lamba-manish/vestrs
   ```

---

## Branch protection (current `main` rules)

Set via `gh api repos/.../branches/main/protection` in slice 13:

- 13 required status checks (the workflow jobs above).
- 1 approving review (admin override during solo dev).
- Linear history (squash-merge only).
- No force-push, no branch deletion.
- `required_conversation_resolution: true`.
- Stale reviews dismissed on new commits.

---

## Cost & teardown

The 1-week demo costs ≤$5/wk:

- t3.small: ~$3.70/wk.
- EIP: free while attached.
- Route53 zone: $0.12/wk.
- S3 (state + backups): trivial.
- SSM Session Manager: free.
- DynamoDB lock table: PAY_PER_REQUEST, trivial.
- Grafana Cloud free tier: free at this volume.

To tear down:

```bash
# 1. Drain release branches so no auto-deploy fires
git push origin :release/production   # delete remote branch
git push origin :release/staging

# 2. terraform destroy per-env first, then bootstrap last
cd infra/terraform/envs/production && terraform destroy
cd ../../bootstrap && terraform destroy

# 3. Manually disassociate the Route53 zone if migrating off AWS
```

---

## When things break

- **`/healthz` returns 5xx** — `aws ssm start-session ...` →
  `cd /opt/vestrs && docker compose -f infra/compose/docker-compose.production.yml --env-file .env.production logs --tail 100 api`.
- **Caddy can't issue cert** — DNS not yet propagated, or the
  challenge port (80) is firewalled. Check
  `docker compose logs caddy` for `acme: failed to receive challenge`.
- **Trivy red on release** — see "Reading a red Trivy job" above.
- **SSM RunCommand can't find instance** — the EC2 IAM instance
  profile must include `AmazonSSMManagedInstanceCore`; agent must be
  online at `aws ssm describe-instance-information`.
- **OIDC AssumeRoleWithWebIdentity 403** — `sub` mismatch. The trust
  policy pins to `repo:lamba-manish/vestrs:ref:refs/heads/release/<env>`
  AND `repo:...:environment:<env>` — both must match the running
  workflow's branch + environment.
