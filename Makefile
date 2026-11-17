.PHONY: install run test lint audit hooks
install:
	python -m pip install -r backend/requirements.txt
	cd frontend && npm install
run:
	cd backend && uvicorn app.main:app --reload

test:
	@if [ -x backend/.venv/bin/python ]; then cd backend && .venv/bin/python -m pytest -q; \
	elif [ -x backend/venv/bin/python ]; then cd backend && venv/bin/python -m pytest -q; \
	else echo "Create backend/.venv or backend/venv with Python 3.11+ first."; exit 1; fi
	cd frontend && npm test
lint:
	cd backend && ruff check app tests && ruff format --check app tests
	cd frontend && npm run lint

audit:
	cd backend && pip-audit -r requirements.txt
	cd frontend && npm audit --audit-level=high
hooks:
	pre-commit install
