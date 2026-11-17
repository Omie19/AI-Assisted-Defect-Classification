# InspectIQ — AI-Assisted Quality Inspection

A full-stack take-home implementation for human-verified, AI-assisted manufacturing defect classification.

### Manufacturing scope

- Factory workspace: Northstar Manufacturing.
- Images may show any visible manufactured product or household object; the selected batch supplies traceability context and does not restrict the image's product family.
- Demo batches are `BATCH-001` / Line 1, `BATCH-002` / Line 2 and `BATCH-003` / Line 3.
- The AI suggests only visible surface defect categories. It does not authenticate a SKU, model, material specification or batch identity from the image.

## Features

- Seeded batches (`BATCH-001` to `BATCH-003`) with product and production-line metadata.
- Quality Engineer and Production Supervisor demo roles. The API enforces the Quality Engineer restriction on uploads, classification, and inspection creation; changing or hiding a frontend control is not the security boundary.
- Live webcam capture or image upload (JPEG/PNG/WebP, 8 MB max), image verification, and local image storage.
- Vision classification through the OpenAI Responses API. The model output is parsed and constrained to `Scratch`, `Dent`, `Paint Issue`, `Missing Component`, or `No Defect`. Unsupported labels fall back to `No Defect` with a visible warning; malformed responses fail for retry.
- Separate `ai_classifications` and `inspections` records linked by a foreign key. The AI prediction, model, confidence, image reference and inspector are persisted when classification succeeds; the inspection stores the human final decision. `was_overridden` is derived server-side, not trusted from the browser. A classification can be submitted only once and only by the inspector who requested it.
- Filterable inspection list and dashboard KPIs. Defect rate = rejected / all inspections. AI acceptance rate = non-overridden / all inspections. Breakdown counts only rejected units by final defect category.
- Pytest coverage for taxonomy parsing and KPI calculations.

## Architecture

- `frontend/`: React + TypeScript + Vite single-page app.
- `backend/`: FastAPI API, SQLAlchemy persistence, OpenAI adapter and validation.
- `backend/app/ai_service.py`: isolates provider calls and untrusted model-output normalization.
- `backend/app/product_scope.py`: shared generic manufacturing workspace and batch-label configuration.
- `backend/app/metrics.py`: pure KPI aggregation logic, independent of HTTP/database concerns.
- `backend/app/models.py`: batches and inspections. The inspection row stores both AI and human decisions so corrections are queryable and auditable.
- Local development defaults to SQLite. Docker Compose runs PostgreSQL 16 and overrides `DATABASE_URL` for a production-like local setup.

## Requirements

- Python 3.11+
- Node.js 20+
- An OpenAI API key for live image classification (the UI/API can start without it, but `/api/classify` returns a safe provider error).
- Docker Compose v2 is optional, for PostgreSQL-based setup.

## Quick start (SQLite)

### 1. Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Put your API key in `backend/.env`:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-6-luna
```

Never put the API key in frontend code or commit `.env`. `DATABASE_URL` is optional; without it the backend uses SQLite. Then start the API:

```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### 2. Frontend (new terminal)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Set `VITE_DEFAULT_USER_ID` in `frontend/.env` to select a seeded demo profile:

```env
VITE_DEFAULT_USER_ID=L040223
```

Use `L040223` for Priya Singh or `L040224` for Alex Morgan. This ID selects a demo profile; it is not a secret. Restart Vite after changing it. Open the URL Vite prints, usually http://localhost:5173.

### 3. Demo roles

The configured `VITE_DEFAULT_USER_ID` selects one of the seeded demo identities:
- Priya Singh — Quality Engineer (can upload/classify/submit)
- Alex Morgan — Production Supervisor (read-only)

Each business request uses an `X-User-Id` header. The backend resolves the name, role and permissions from its hard-coded demo identity directory and enforces Quality Engineer permissions on write endpoints. The internal `GET /api/users/me` route returns the frontend profile and is hidden from the generated Swagger schema.

```http
GET /api/users/me
X-User-Id: L040223
```

The profile includes `user_id`, `name`, `role`, `email`, `department`, `employee_type`, `permissions`, and `active`. Unknown IDs are rejected. This is not production authentication; replace it with a verified identity in production.

## PostgreSQL with Docker Compose

Create `backend/.env` first (Docker Compose expects this file):

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Add OPENAI_API_KEY to backend/.env
```

Then run from the repository root:

```bash
docker compose up --build
```

Frontend: http://localhost:5173 · API docs: http://localhost:8000/docs

## Tests

With a Python 3.11+ backend virtual environment created, backend developer dependencies installed from `backend/requirements-dev.txt`, and frontend dependencies installed with `npm install`, run all backend and frontend tests with:

```bash
make test
```

Run this from the repository root or from `backend/`. The Makefile selects `backend/.venv` or `backend/venv` directly, so activating the environment is not required.

To run only the frontend tests, from the repository root run:

```bash
cd frontend && npm test
```

This runs Vitest in one-shot mode using the test files under `frontend/src/`.

## Lint and security

Install developer tools from `backend/` before running checks:

```bash
cd backend && python -m pip install -r requirements-dev.txt
```

Run lint and dependency checks:

```bash
cd backend && ruff format app tests && ruff check app tests && pip-audit -r requirements.txt
cd ../frontend && npm run lint && npm audit --audit-level=high
```

The `.pre-commit-config.yaml` wires a local hook to `scripts/pre-commit-checks.sh`. Install the required pre-commit hook once from the repository root:

```bash
python -m pip install -r backend/requirements-dev.txt
pre-commit install
```

The hook runs backend tests, Ruff lint and formatting, `pip-audit`, frontend tests, ESLint and `npm audit` before each commit. Verify installation with `pre-commit run --all-files`.

## Vision model and cost

Provider: OpenAI. Model: `gpt-6-luna`, configured through `OPENAI_MODEL`. It accepts image input and is designed for efficient, focused tasks. The app makes one synchronous model request per classification; the timeout is 30 seconds and one SDK retry is enabled. Provider errors are returned as a safe `502` message, leaving the uploaded photo available for retry. See the [GPT-6 Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna), [image input guide](https://developers.openai.com/api/docs/guides/images-vision) and [current pricing](https://developers.openai.com/api/docs/pricing). Actual cost depends on image dimensions/detail and prompt/output tokens; record actual usage from the API usage dashboard rather than assuming a fixed per-image cost.

## Model choice and architecture decisions

GPT-6 Luna fits this prototype because each request analyzes one image, selects from five defect labels, and returns a small JSON result. Its image input and focus on efficient tasks suit this constrained classification job; the workflow does not require open-ended reasoning. The selection is a design choice for a prototype, not a claim of validated inspection accuracy. The model's suggestions still require human review.

The architecture keeps the provider adapter (`ai_service.py`) separate from FastAPI routes, image validation, taxonomy normalization and SQLAlchemy persistence. This makes the model configurable through `OPENAI_MODEL` without changing the inspection workflow. AI classifications and final inspections use separate records so the original prediction remains auditable after an engineer override. Calls remain synchronous for this small demo; a production workflow may need a queue, latency monitoring and evaluation against labeled inspection data.

Pre-commit checks are wired through `.pre-commit-config.yaml` to the local `project-checks` hook, which runs `scripts/pre-commit-checks.sh` before each commit. The script runs backend tests, Ruff lint and formatting, `pip-audit`, frontend tests, ESLint and `npm audit`. Install the hook with `pre-commit install`; run it manually with `pre-commit run --all-files`.

## Known limitations / deliberate shortcuts

- Demo user profiles are hard-coded and `X-User-Id` is not authentication. It demonstrates server-side role checks but must be replaced with a verified identity provider in production.
- Images are stored on the backend filesystem (a Docker volume in Compose), not object storage. A production system should use S3-compatible storage, signed URLs, retention controls and malware/content scanning.
- The model confidence is a self-reported estimate, not a calibrated probability. It is optional and displayed as such.
- Unsupported model labels map to `No Defect` as a safe taxonomy fallback, with a warning and mandatory human confirmation. Malformed output is rejected for retry. A production workflow could add a separate `Needs review` state rather than conflating fallback with a clean result.
- No batch CRUD, pagination, deletion, full authentication, production deployment, or background job queue is included (outside the core time-boxed scope). Classification is synchronous; the UI shows a loading state.
- SQLite is the default for quick setup. Use Compose for PostgreSQL. Schema creation is done with SQLAlchemy `create_all`; a production project should add Alembic migrations.

## Git setup

```bash
git init
git add .
git commit -m "Build AI-assisted quality inspection workflow"
```

A `.gitignore` excludes API secrets, local databases, uploads, virtual environments, build outputs and dependency folders.
