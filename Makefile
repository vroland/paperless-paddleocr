.PHONY: check test paperless-test dev-build dev-up dev-down dev-restart dev-logs dev-reset

COMPOSE = docker compose --env-file dev/.env -f dev/compose.yaml

check:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest -q

paperless-test:
	uv run --group paperless pytest -q tests/paperless

dev-build:
	$(COMPOSE) build

dev-up:
	test -f dev/.env || cp dev/.env.example dev/.env
	$(COMPOSE) up -d

dev-down:
	$(COMPOSE) down

dev-restart:
	$(COMPOSE) restart webserver

dev-logs:
	$(COMPOSE) logs -f webserver

dev-reset:
	$(COMPOSE) down -v
