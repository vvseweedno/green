.PHONY: setup verify-data test research demo api frontend judge

setup:
	python -m pip install -e '.[dev]'

verify-data:
	python scripts/verify_dataset.py data/raw

test:
	pytest -q

research:
	python research/run_experiments.py --dataset data/raw

demo:
	@echo "Use: python scripts/reproduce_demo.py --request <request.json> --dataset data/raw"

api:
	uvicorn carbon_mrv.api.app:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm install && npm run dev

judge:
	python scripts/judge_preflight.py
