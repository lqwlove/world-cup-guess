.PHONY: up down seed migrate test logs prod-up prod-down prod-seed prod-logs

COMPOSE_PROD = docker compose -f docker-compose.prod.yml --env-file .env.production

up:
	cp -n .env.example .env 2>/dev/null || true
	docker compose up --build -d

down:
	docker compose down

seed:
	docker compose exec api python -m app.scripts.seed

migrate:
	docker compose exec api alembic upgrade head

test:
	cd services/api && python -m pytest -q

logs:
	docker compose logs -f api worker web

prod-up:
	test -f .env.production || (echo "先执行: cp .env.production.example .env.production" && exit 1)
	$(COMPOSE_PROD) up -d --build

prod-down:
	$(COMPOSE_PROD) down

prod-seed:
	$(COMPOSE_PROD) exec api python -m app.scripts.seed

prod-logs:
	$(COMPOSE_PROD) logs -f api worker web
