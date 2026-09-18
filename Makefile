.PHONY: test seed run-api run-web install

install:
	pip install -r requirements.txt

seed:
	python -m db.seed

test:
	pytest tests/ -v

run-api:
	python -m uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload

run-web:
	cd apps/web && npm run dev
