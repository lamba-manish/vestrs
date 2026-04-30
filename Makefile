SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose -f infra/compose/docker-compose.yml --env-file .env

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

bootstrap: ## copy example env files for local dev
	@test -f .env || cp .env.local.example .env
	@test -f apps/api/.env || cp apps/api/.env.example apps/api/.env
	@test -f apps/web/.env || cp apps/web/.env.example apps/web/.env
	@echo "env files in place"

up: bootstrap ## build and start the local stack
	$(COMPOSE) up --build -d
	@$(COMPOSE) ps

down: ## stop the local stack
	$(COMPOSE) down

restart: ## restart the local stack
	$(MAKE) down
	$(MAKE) up

logs: ## tail logs
	$(COMPOSE) logs -f --tail=200

ps: ## list services
	$(COMPOSE) ps

api-shell: ## shell into the api container
	$(COMPOSE) exec api /bin/bash

web-shell: ## shell into the web container
	$(COMPOSE) exec web /bin/sh

api-test: ## run backend tests inside the container
	$(COMPOSE) exec api uv run pytest -q

api-lint: ## run backend lint + type checks
	$(COMPOSE) exec api bash -c "uv run ruff check . && uv run black --check . && uv run mypy app"

web-test: ## run frontend tests
	$(COMPOSE) exec web pnpm test --run

web-lint: ## run frontend lint + type checks
	$(COMPOSE) exec web sh -c "pnpm lint && pnpm typecheck"

clean: ## stop stack and remove volumes (DESTRUCTIVE)
	$(COMPOSE) down -v

# ---------- quality gates ----------

hooks-install: ## install pre-commit framework + git hooks (pre-commit, commit-msg, pre-push)
	@command -v pre-commit >/dev/null || uv tool install pre-commit
	pre-commit install --install-hooks
	pre-commit install --hook-type commit-msg
	pre-commit install --hook-type pre-push
	@echo "pre-commit hooks installed (pre-commit + commit-msg + pre-push)"

hooks-run: ## run all pre-commit hooks across the repo
	pre-commit run --all-files

hooks-update: ## bump pinned hook versions
	pre-commit autoupdate

gitleaks: ## scan repo for secrets (no commit needed)
	@command -v gitleaks >/dev/null && gitleaks detect --source . --redact -v \
	 || docker run --rm -v "$(PWD)":/repo zricethezav/gitleaks:v8.21.2 detect --source /repo --redact -v

trivy: ## scan built api+web images locally (HIGH+CRITICAL fail)
	@docker build -t vestrs-api:scan --target runtime apps/api
	@docker build -t vestrs-web:scan --target builder apps/web
	@for img in vestrs-api:scan vestrs-web:scan; do \
	  echo "--- trivy $$img ---"; \
	  docker run --rm -v "$(PWD)/.trivyignore:/work/.trivyignore" \
	    -v /var/run/docker.sock:/var/run/docker.sock \
	    aquasec/trivy:latest image --severity HIGH,CRITICAL --ignore-unfixed \
	    --ignorefile /work/.trivyignore --exit-code 1 $$img || exit 1; \
	done

# ---------- observability (slice 14C) ----------

obs-up: ## bring up local Prometheus + Grafana + exporters (compose profile)
	$(COMPOSE) --profile observability up -d
	@echo
	@echo "  Prometheus  → http://localhost:9090"
	@echo "  Grafana     → http://localhost:3001  (admin / admin)"
	@echo "  cAdvisor    → http://localhost:8080  (port-forwarded by compose)"

obs-down: ## stop the observability profile services only
	$(COMPOSE) --profile observability stop \
	  prometheus grafana node-exporter cadvisor postgres-exporter redis-exporter blackbox-exporter

obs-logs: ## tail observability logs
	$(COMPOSE) --profile observability logs -f --tail=100 \
	  prometheus grafana node-exporter cadvisor postgres-exporter redis-exporter blackbox-exporter

# ---------- release / deploy (slice 14A) ----------

deploy-staging: ## run deploy.sh against staging (must be on target host)
	bash infra/scripts/deploy.sh staging

deploy-prod: ## run deploy.sh against production (must be on target host)
	bash infra/scripts/deploy.sh production

compose-config-staging: ## render the staging compose file with vars expanded
	docker compose -f infra/compose/docker-compose.staging.yml --env-file .env.staging config

compose-config-prod: ## render the prod compose file with vars expanded
	docker compose -f infra/compose/docker-compose.production.yml --env-file .env.production config

# ---------- e2e ----------

e2e: ## run Playwright against the running compose stack
	$(COMPOSE) exec web pnpm e2e

e2e-install: ## install Playwright browsers inside the web container (first-time setup)
	$(COMPOSE) exec web pnpm exec playwright install --with-deps chromium

# ---------- ci-local ----------

ci-local: ## run the full CI matrix locally (lint+types+tests+build, BE+FE)
	@echo "==> backend lint + types"
	$(MAKE) api-lint
	@echo "==> backend tests"
	$(MAKE) api-test
	@echo "==> frontend lint + types"
	$(MAKE) web-lint
	@echo "==> frontend tests"
	$(MAKE) web-test
	@echo "==> frontend build"
	$(COMPOSE) exec web pnpm build
	@echo "==> gitleaks"
	$(MAKE) gitleaks
	@echo "ci-local: all gates passed"

.PHONY: help bootstrap up down restart logs ps api-shell web-shell api-test api-lint web-test web-lint clean hooks-install hooks-run hooks-update gitleaks trivy e2e e2e-install ci-local deploy-staging deploy-prod compose-config-staging compose-config-prod obs-up obs-down obs-logs
