.PHONY: start stop status migrate seed build-web install-api install-web test

start:
	./start.sh start

stop:
	./start.sh stop

status:
	./start.sh status

build-web:
	./start.sh build-web

install-api:
	cd services/api && pip install -r requirements.txt

install-web:
	cd apps/web && npm ci

migrate:
	cd services/api && alembic upgrade head

seed:
	cd services/api && python -m app.scripts.seed

test:
	cd services/api && python -m pytest -q
