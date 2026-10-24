.PHONY: install up api web ingest types check check-api check-web check-types test-api test-web

install:
	cd backend && uv sync
	cd frontend && npm ci

up:
	docker compose up --build

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

# Hits the network (Elexon). Writes backend/data/snapshot/.
ingest:
	cd backend && uv run python -m scripts.ingest

types:
	cd backend && uv run python -m scripts.export_openapi
	cd frontend && npm run types

check: check-api check-web check-types

check-api:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app scripts && uv run pytest -q

check-web:
	cd frontend && npm run lint && npm run build && npm test

# Regenerates both type artefacts into a temp dir and fails if the committed ones are stale. No git needed.
check-types:
	@set -e; tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
	(cd backend && uv run python -m scripts.export_openapi "$$tmp/openapi.json"); \
	(cd frontend && npx --no-install openapi-typescript "$$tmp/openapi.json" -o "$$tmp/schema.d.ts"); \
	if diff -u backend/openapi.json "$$tmp/openapi.json" && diff -u frontend/src/api/schema.d.ts "$$tmp/schema.d.ts"; \
	then echo "API types up to date"; else echo "API types are stale: run 'make types'"; exit 1; fi

test-api:
	cd backend && uv run pytest

test-web:
	cd frontend && npm test
