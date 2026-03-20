.PHONY: up down build migrate seed harvest synthesize classify test test-backend test-frontend logs shell-api shell-db shell-worker lint format

# ──────────────────────────────────────────────
# Stack Management
# ──────────────────────────────────────────────

up:
	docker compose up -d --build
	@echo "✅ Stack running. Frontend: http://localhost:3000 | API docs: http://localhost:8000/docs | Qdrant: http://localhost:6333/dashboard"

down:
	docker compose down

down-clean:
	docker compose down -v --remove-orphans
	@echo "⚠️  All volumes deleted. Run 'make migrate && make seed' to restore."

build:
	docker compose build

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────

migrate:
	docker compose exec api alembic upgrade head
	@echo "✅ Migrations applied."

migrate-down:
	docker compose exec api alembic downgrade -1

migration-new:
	@read -p "Migration name: " name; \
	docker compose exec api alembic revision --autogenerate -m "$$name"

seed:
	docker compose exec api python scripts/seed_taxonomy.py
	@echo "✅ Taxonomy seeded."

# ──────────────────────────────────────────────
# Agent Pipeline (Manual Triggers)
# ──────────────────────────────────────────────

harvest:
	docker compose exec api python -c "from agents.harvester.scraper import run_harvest; import asyncio; asyncio.run(run_harvest())"
	@echo "✅ Harvest complete. Check logs for summary."

synthesize:
	docker compose exec api python -c "from agents.synthesizer.extractor import run_extraction; import asyncio; asyncio.run(run_extraction())"
	@echo "✅ Synthesis complete."

classify:
	docker compose exec api python -c "from agents.taxonomist.mapper import run_classification; import asyncio; asyncio.run(run_classification())"
	@echo "✅ Classification complete."

pipeline:
	$(MAKE) harvest
	$(MAKE) synthesize
	$(MAKE) classify
	@echo "✅ Full pipeline run complete."

backfill-embeddings:
	docker compose exec api python scripts/backfill_embeddings.py

# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

test:
	$(MAKE) test-backend
	$(MAKE) test-frontend
	@echo "✅ All tests complete."

test-backend:
	docker compose exec api pytest tests/ -v --tb=short

test-frontend:
	docker compose exec frontend npm run test

# ──────────────────────────────────────────────
# Development Shells
# ──────────────────────────────────────────────

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U postgres -d workforce_ai

shell-worker:
	docker compose exec worker bash

# ──────────────────────────────────────────────
# Code Quality
# ──────────────────────────────────────────────

lint:
	docker compose exec api ruff check backend/
	docker compose exec frontend npm run lint

format:
	docker compose exec api ruff format backend/
	docker compose exec frontend npm run format

# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

health:
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "❌ API not responding"
	@curl -s http://localhost:6333/collections | python3 -m json.tool || echo "❌ Qdrant not responding"
	@docker compose exec redis redis-cli ping || echo "❌ Redis not responding"
