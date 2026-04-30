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
