# Makefile

.PHONY: dev down logs audit shell db-migrate

dev:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f worker api

# run an audit from CLI: make audit URL=https://github.com/user/repo
audit:
	python scripts/run_audit_cli.py $(URL)

shell:
	docker compose exec api bash

db-migrate:
	docker compose exec api alembic upgrade head

test:
	pytest tests/ -v