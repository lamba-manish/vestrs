# vestrs-api

FastAPI service for the Vestrs onboarding platform.

See [`../../CLAUDE.md`](../../CLAUDE.md) for project conventions.

## Local development (outside docker)

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload
```

If you run outside the compose stack, change `postgres` to `localhost` and
`redis` to `localhost` in your `.env`.

## Tests, lint, types

```bash
uv run pytest -q
uv run ruff check .
uv run black --check .
uv run mypy app
```
