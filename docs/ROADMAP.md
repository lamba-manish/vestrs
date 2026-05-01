# Roadmap — explicit out-of-scope + good-to-have

A take-home brief is a slice of what a real platform needs. This doc
records what the codebase **does not** do today, why it was reasonable
to leave it out for the assignment, and what shape the fix would take.
Most items here are 1–4 hours of work each; none are blocking the
demo.

## Tier 1 — would address before a real production ship

| Item | Why | Approach |
|---|---|---|
| **Audit-log immutability** | The audit log is the system of record. Today the API user can `UPDATE`/`DELETE` rows. | Postgres trigger that raises on `UPDATE`/`DELETE` of `audit_logs` + a daily hash-chain checkpoint job. |
| **Row-level security** | Auth is enforced only in the API. Bypass = full table read. | `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + per-table policies keyed by `current_setting('app.user_id')`. |
| **GDPR delete + export** | EU/UK users can't recover or remove their data. | `POST /me/delete` (soft-delete with PII anonymisation) + `GET /me/export` (signed JSON tarball). |
| **Per-email login rate limit** | Today's per-IP limit is 30/5m — a botnet at 30 IPs ×30 = 900/min/email. | Add a `bucket="auth:login:email:<sha256>"` second window. |
| **DLQ on the worker** | Failed welcome / accreditation jobs vanish after retries. | ARQ `failed_jobs` queue + an alertmanager rule on its depth. |
| **Email verification on signup** | Welcome email lands but the address isn't proven owned. | Token table + `/auth/verify-email/<token>` route, dashboard nag until verified. |

## Tier 2 — credibility-grade additions

| Item | Why |
|---|---|
| **PEP / sanctions screening** | OFAC + UN + EU lists are mandatory for cross-border investment. Today's KYC mock skips it; real KYC vendors have a `screen()` API on the same call. |
| **Suitability questionnaire** | Reg D / FCA / SEBI all require a documented risk-tolerance assessment before placing investments. |
| **T&Cs + privacy consent log** | Where is the user's consent record? Currently there isn't one. |
| **Source-of-funds capture** | AMLD5 / FATF requirement; the investment endpoint takes an amount but never asks where it came from. |
| **Customer Due Diligence refresh** | Annual / biennial re-screening on existing customers. |
| **Multi-currency** | Currency is a string field on the bank account. Real cross-border needs FX rate snapshots + reconciliation. |
| **Segregation of duties** | Currently the same user creates and implicitly approves their own investment. Real platforms gate amounts above a threshold behind a second approver. |
| **Legal entity types** | Onboarding only handles individuals. Trusts, family offices, and corporate accounts need different field sets. |

## Tier 3 — operational polish

| Item | Why |
|---|---|
| **EC2 tag-based instance lookup at deploy time** | The static `AWS_INSTANCE_ID_PRODUCTION` repo variable goes stale on rebuilds. Replace with `aws ec2 describe-instances --filters Name=tag:Env,Values=production`. Pairs with the slice-25 IAM tag scoping. |
| **Backup restore drill in CI** | `pg_dump` runs nightly; we have never proved a restore works. Add a weekly GH Actions job that restores into a scratch DB and runs a tiny smoke query. |
| **SBOM + cosign signing** | GHCR images are pulled by tag. A compromised CI could publish a tampered image. Sign with cosign, verify on pull, and emit an SPDX SBOM per build. |
| **CDN in front of the static FE** | Caddy serves `dist/` from one EC2 box. Asia-Pacific users hit the box directly. CloudFront caches and absorbs DDoS. |
| **Loki shipping to S3** | 7-day on-box retention is fine for ops but not compliance. Stream to an immutable-bucket Loki backend with a long retention policy. |
| **Drift detection** | `terraform plan` on a schedule + alert on diff. driftctl works for the AWS side. |
| **Image digest pinning at deploy** | `compose pull` follows the floating tag. Pin to digest in the deploy job so a re-tag from elsewhere can't ship to prod. |

## Tier 4 — product / platform

| Item | Why |
|---|---|
| **Frontend error tracking** | Sentry / PostHog Errors. One bad render goes silent today. |
| **Funnel analytics** | PostHog or Mixpanel — we have no idea where users drop off in the 5-step flow. |
| **Visual regression tests** | Chromatic / Percy. Playwright covers behaviour, not pixels. |
| **i18n** | Single locale hardcoded. Cross-border product, multilingual users. |
| **Admin / support console** | Read-only view ops can use to investigate a stuck user. Today the answer is `psql`. |
| **Tax document generation** | 1099 / K-1 / P11D depending on jurisdiction. |
| **Customer support chatbot** | Anthropic / OpenAI tool-use over the audit log + KYC + investments tables, scoped to the user's own data. |
| **Workflow orchestration with Temporal** | Multi-step flows like accreditation (submit → poll → resolve → email) currently hand-roll re-enqueue logic. Temporal would express the saga directly with built-in idempotency, retries, and history. |
| **Push notifications** | Email is the only outbound channel. Web Push or Apple/Google notifications would close the loop on long-running async actions. |
| **Mobile app** | The PWA is mobile-friendly but there's no native shell yet. Capacitor or React Native around the existing FE bundle would ship in a sprint. |

## Tier 5 — nice signals for reviewers

| Item | Why |
|---|---|
| **Demo video** | Walks through signup → KYC → accreditation (each SEC path) → bank → invest → audit. ~2-3 min. |
| **Architecture decision records (ADRs)** | One short markdown per key decision (Vite over Next.js, single EC2 over Fargate, on-box Grafana over Cloud, etc.). The reasoning lives in commits today; ADRs make it findable. |
| **Performance budget** | Bundle size, LCP, INP targets in the README, enforced by Lighthouse CI. |
| **Web vitals dashboard** | The Grafana stack already has Loki — push web-vitals from the FE to a `/web-vitals` ingest endpoint and graph p75 LCP / INP / CLS. |

## Out of scope (and intentionally so)

- **2FA / MFA** — assignment scope is signup with email + password. Adding TOTP / WebAuthn is a tracked Tier-2 followup.
- **Live vendor integration** — the brief explicitly mocks KYC / accreditation / bank. The adapter Protocol shape is the integration plan.
- **Self-serve account closure** — covered by the GDPR delete in Tier 1.
