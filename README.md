# InspectIQ — AI-Assisted Quality Inspection

A full-stack take-home implementation for human-verified, AI-assisted manufacturing defect classification.

## Features

- Seeded batches (`BATCH-001`, `BATCH-002`) with product and production-line metadata.
- Quality Engineer and Production Supervisor demo roles. The API enforces the Quality Engineer restriction on uploads, classification, and inspection creation; changing or hiding a frontend control is not the security boundary.
- Image upload (JPEG/PNG/WebP, 8 MB max), image verification, and local image storage.
- Vision classification through the OpenAI Responses API. The model output is parsed and constrained to `Scratch`, `Dent`, `Paint Issue`, `Missing Component`, or `No Defect`. Malformed/unsupported outputs fail closed to `No Defect` with a visible warning so a human must review the result.
- Separate `ai_classifications` and `inspections` records linked by a foreign key. The AI prediction, model, confidence, image reference and inspector are persisted when classification succeeds; the inspection stores the human final decision. `was_overridden` is derived server-side, not trusted from the browser. A classification can be submitted only once and only by the inspector who requested it.
- Filterable inspection list and dashboard KPIs. Defect rate = rejected / all inspections. AI acceptance rate = non-overridden / all inspections. Breakdown counts only rejected units by final defect category.
- Pytest coverage for taxonomy parsing and KPI calculations.

## Architecture

- `frontend/`: React + TypeScript + Vite single-page app.
- `backend/`: FastAPI API, SQLAlchemy persistence, OpenAI adapter and validation.
- `backend/app/ai_service.py`: isolates provider calls and untrusted model-output normalization.
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
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Put your API key in `backend/.env`:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Never put the API key in frontend code or commit `.env`. Then start the API:

```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### 2. Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### 3. Demo roles

The left navigation's settings icon switches between the seeded demo identities:
- Priya Singh — Quality Engineer (can upload/classify/submit)
- Alex Morgan — Production Supervisor (read-only)

The API uses `X-User-Role` and `X-User-Name` headers as a deliberately lightweight demo identity mechanism. This is not production authentication. The role check is enforced by FastAPI dependencies on write endpoints. In production, replace these headers with a verified identity from an authentication provider; never trust a client-supplied role header.

## PostgreSQL with Docker Compose

Create `backend/.env` first (Docker Compose expects this file):

```bash
cp backend/.env.example backend/.env
# Add OPENAI_API_KEY to backend/.env
```

Then run from the repository root:

```bash
docker compose up --build
```

Frontend: http://localhost:5173 · API docs: http://localhost:8000/docs

## Tests, lint and security

```bash
cd backend && python -m pytest -q
cd ../frontend && npm test
```

Checks:

```bash
cd backend && ruff format app tests && ruff check app tests && pip-audit -r requirements.txt
cd ../frontend && npm run lint && npm audit --audit-level=high
```

Install the required pre-commit hook once from the repository root:

```bash
python -m pip install pre-commit
pre-commit install
```

The `.pre-commit-config.yaml` hook runs backend tests, Ruff formatting and lint checks, `pip-audit`, frontend tests, ESLint and `npm audit` before each commit. Verify installation with `pre-commit run --all-files`. The hook intentionally fails if dependencies have not been installed or if a security audit reports a vulnerability at the configured severity.

## Vision model and cost

Provider: OpenAI. Default model: `gpt-4.1-mini`, configured through `OPENAI_MODEL`. It accepts image input and is a cost-conscious choice for a small prototype. The app makes one synchronous model request per classification; the timeout is 30 seconds and one SDK retry is enabled. Provider errors are returned as a safe `502` message, leaving the uploaded photo available for retry. Check the current model availability and pricing before running the exercise: https://platform.openai.com/docs/pricing and https://platform.openai.com/docs/guides/images-vision. Actual cost depends on image dimensions/detail and prompt/output tokens; record actual usage from the API usage dashboard rather than assuming a fixed per-image cost.

## Known limitations / deliberate shortcuts

- Demo role headers are not authentication. They demonstrate server-side authorization logic but must be replaced with signed/verified identity claims for production.
- Images are stored on the backend filesystem (a Docker volume in Compose), not object storage. A production system should use S3-compatible storage, signed URLs, retention controls and malware/content scanning.
- The model confidence is a self-reported estimate, not a calibrated probability. It is optional and displayed as such.
- Unsupported or malformed model output maps to `No Defect` only as a safe taxonomy fallback, accompanied by a warning and mandatory human confirmation. A production workflow could add a separate `Needs review` state rather than conflating fallback with a clean result.
- No batch CRUD, pagination, deletion, full authentication, production deployment, or background job queue is included (outside the core time-boxed scope). Classification is synchronous; the UI shows a loading state.
- SQLite is the default for quick setup. Use Compose for PostgreSQL. Schema creation is done with SQLAlchemy `create_all`; a production project should add Alembic migrations.

## Git setup

```bash
git init
git add .
git commit -m "Build AI-assisted quality inspection workflow"
```

A `.gitignore` excludes API secrets, local databases, uploads, virtual environments, build outputs and dependency folders.
