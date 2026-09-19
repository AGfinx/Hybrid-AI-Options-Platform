.PHONY: test seed run-api run-web install verify-e2e docker-up docker-down

install:
	pip install -r requirements.txt
	cd apps/web && npm install

seed:
	python -m db.seed

test:
	pytest tests/ -v

verify-e2e:
	python tests/verify_e2e.py

run-api:
	python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload

run-web:
	cd apps/web && npm run dev

build-web:
	cd apps/web && npm run build

docker-up:
	docker compose -f infra/docker-compose.yml up --build -d

docker-down:
	docker compose -f infra/docker-compose.yml down
