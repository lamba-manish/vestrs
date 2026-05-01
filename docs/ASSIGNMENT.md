# Assignment coverage

Map from the original brief to the implementation, plus the
non-obvious requirements the brief hinted at and how they're
addressed.

## The brief

> Build a system where a user can:
> 1. Sign up / onboard
> 2. Complete KYC/AML/Liveliness check (mocked API)
> 3. Verify Investor Accreditation (mocked API)
> 4. Link a bank account (mocked API)
> 5. Make an investment

> Audit Log (IMPORTANT) — Track KYC attempts, Investor Accreditation,
> Bank linking, Investment. Each log should include: timestamp, user,
> action, status.

> UI (Basic but usable) — Simple frontend, clear loading / success /
> failure states.

> Submission — GitHub repo, demo video, README explaining architecture
> decisions, trade-offs, and assumptions.

## Mapping

| Requirement | Where it lives | Notes |
|---|---|---|
| **Signup with name, email, country (nationality + domicile), phone** | `apps/web/src/routes/{signup,onboarding/profile}.tsx` + `POST /api/v1/auth/signup` + profile endpoints | Argon2id password hashing, JWT access + refresh in httpOnly cookies, refresh-token rotation with reuse detection. |
| **KYC / AML / Liveliness mock** | `apps/api/app/adapters/kyc/` + `POST /api/v1/kyc` | Returns `success` / `failure` / `pending`. Retry handling — three attempts, audit-logged retries (`KYC_RETRY_BLOCKED` / `KYC_RETRY_EXHAUSTED`). |
| **Accreditation mock, can take 12-48h** | `apps/api/app/adapters/accreditation/` + `POST /api/v1/accreditation` | Async: submit returns 202 PENDING; ARQ worker polls + resolves + writes the terminal audit row. **3 SEC-recognised paths** (income / net-worth / professional cert) modelled — see Hidden requirement #1 below. |
| **Bank link mock with masked details** | `apps/api/app/adapters/bank/` + `POST /api/v1/bank/link` | Stores last_four + currency + bank name only. No full account number ever touches the DB. |
| **Investment with balance check** | `POST /api/v1/investments` | `Idempotency-Key` required. Validates the bank's balance vs amount; on insufficient balance writes `INVESTMENT_BLOCKED` with reason. Money is `Decimal` end-to-end on the wire and `NUMERIC(20, 4)` in Postgres. |
| **Audit log with timestamp / user / action / status** | `apps/api/app/models/audit_log.py` + `apps/web/src/routes/audit.tsx` | Same-transaction writes from each service. Plus `request_id`, `ip`, `user_agent`, structured `metadata` JSONB. UI humanises the SCREAMING_SNAKE action codes — `INVESTMENT_CREATED` reads "Investment placed". |
| **UI loading / success / failure states** | All onboarding routes | Skeletons during fetch, sonner toasts on action results, per-`error.code` user copy via `lib/error-messages.ts`. |
| **GitHub repo** | <https://github.com/lamba-manish/vestrs> | Public. |
| **README explaining decisions, trade-offs, assumptions** | `README.md` + `docs/ARCHITECTURE.md` + `docs/DEPLOYMENT.md` + `docs/SECURITY.md` + `docs/RUNBOOK.md` + `docs/ROADMAP.md` | This file is part of that set. |
| **Demo video** | Attached separately to the submission email. | |

## Hidden requirements caught from a careful read

### 1. The SEC accredited-investor link is a hint, not a footnote

The brief contains a link to <https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/accredited-investors>. That guide describes **three** distinct qualification paths. A generic "submit accreditation" button would have ignored the signal. Slice 29 reflects all three:

- **Income test** — ≥$200k individual / ≥$300k joint, sustained 2+ years, with a reasonable expectation of the same in the current year.
- **Net-worth test** — ≥$1M, must exclude primary residence (we explicitly attest the exclusion).
- **Professional certification** — Series 7, 65, or 82 (the 2020 Reg D amendment).

The accreditation form on `/onboarding/accreditation` is a three-card picker with per-path validation that mirrors the SEC thresholds 1:1 (`apps/api/app/schemas/accreditation.py` and the matching `apps/web/src/lib/schemas/accreditation.ts`). The mock vendor uses the user's attestation to decide the eventual outcome — fail conditions surface as user-friendly reasons (`income_threshold_not_met`, `primary_residence_not_excluded`, etc.) which the UI then humanises before display.

### 2. "Cross-border" means more than just the word "international"

Domicile + nationality are captured separately on the profile (a real cross-border product needs both). E.164 phone normalisation is handled with `phonenumbers`. Currency is a first-class field on the bank account with a 30-currency picker. Tax-residency capture is on the roadmap (Tier 2).

### 3. "User invests from bank account directly to escrow account or law-firm pooling account"

The wording is specific. The investment record persists `escrow_reference` (a string) and the audit metadata for `INVESTMENT_CREATED` includes `amount`, `currency`, and `escrow_reference`. The audit-log UI surfaces this as `USD 1500.00 · escrow escrow-abc123`.

### 4. "Validate sufficient balance"

Every investment endpoint call:
- locks the bank-account row for update,
- computes available balance (`balance - sum(pending+placed investments)`),
- if insufficient, raises `InsufficientBalanceError` and writes `INVESTMENT_BLOCKED` with `reason: "insufficient_balance"`.

### 5. "Retries / failure states"

Every mocked vendor's failure is reachable deterministically by an email tag (`+kyc_fail`, `+acc_fail`, `+bank_fail`). KYC retries are gated by attempts; exhaustion writes `KYC_RETRY_EXHAUSTED`. Accreditation retries that come in while a check is in flight write `ACCREDITATION_RETRY_BLOCKED` with `reason: "in_flight"`. Bank link retries write `BANK_LINK_BLOCKED`.

## Trade-offs we made

- **Single EC2 box** instead of multi-AZ / Fargate. Production behaviour is correct (HA, replication, restore drills) but capacity isn't. Roadmap Tier 1.
- **Welcome email best-effort** (BackgroundTasks + ARQ); never blocks signup. Email verification is the natural Tier-1 followup.
- **Mocked vendors** with deterministic failure paths; the adapter Protocol is the integration plan for live vendors.
- **Branch-protection-with-admin-bypass** instead of strict reviewer gates on `release/production`. Solo-dev workflow with a real approval gate at the GitHub Environment is the actual control point.
- **Self-host Grafana** instead of Grafana Cloud. Cleaner demo (no SaaS account required); Cloud agent remains an opt-in profile.

## Assumptions

- The brief specifies "mocked APIs" so KYC / Accreditation / Bank vendors are **always** mocked, including in production. Real vendor swap-in is a Protocol implementation away.
- Single-currency investment — the `currency` field exists end-to-end but FX is out of scope.
- Single-region (`ap-south-1`). All AWS resources, the Caddy TLS challenge, the Route53 zone — all in one region.
- Solo-dev workflow — branch protection allows admin bypass; a team setup would set `enforce_admins: true`.
