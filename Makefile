.PHONY: up down migrate collect features ml backtest

up:
	docker compose up -d db
	@echo "Waiting for DB..."
	@sleep 5
	docker compose up -d

down:
	docker compose down

migrate:
	docker compose run --rm collector alembic upgrade head

collect:
	python -m services.collector.main

features:
	python -m services.feature_store.main

ml:
	python -m services.ml_module.main

backtest:
	python -m services.backtester.main
