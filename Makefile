.PHONY: install run test lint audit hooks
install:
	python -m pip install -r backend/requirements.txt
	cd frontend && npm install
run:
	cd backend && uvicorn app.main:app --reload

test:
	cd backend && python -m pytest -q
	cd frontend && npm test
lint:
	cd backend && ruff check app tests && ruff format --check app tests
	cd frontend && npm run lint

audit:
	cd backend && pip-audit -r requirements.txt
	cd frontend && npm audit --audit-level=high
hooks:
	pre-commit install
