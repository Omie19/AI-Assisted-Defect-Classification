<<<<<<< Updated upstream
# AI-Assisted-Defect-Classification
A system that would help manufacturing teams track production batches and quality inspections. 
=======
# InspectIQ — AI-Assisted Manufacturing Quality Inspection

A full-stack take-home implementation for human-verified, AI-assisted defect classification across **general manufactured products**. The image workflow accepts any physical product, including household objects used as test fixtures (for example, mugs, bottles, boxes, tools, containers and furniture parts).

## Manufacturing scope

- Factory workspace: Northstar Manufacturing.
- Product scope: any visible physical product or manufactured item.
- Household objects and stock photos are supported as test fixtures (for example, mugs, bottles, boxes, tools, plastic containers, toys and furniture parts).
- The classifier does not require a product-family match and does not reject an image merely because it is not a particular factory product.
- Seed batches: `BATCH-001` / Line 1, `BATCH-002` / Line 2 and `BATCH-003` / Line 3. Batch selection provides traceability context only; it does not restrict the product shown in the uploaded image.
- Accepted visual outcomes: Scratch, Dent, Paint Issue, Missing Component or No Defect.

The AI provides a visual defect suggestion, not product authentication. It does not verify a SKU, model, material specification or batch identity from the photo.

## Features

- Seeded batches (`BATCH-001` to `BATCH-003`) for general product inspection across three production lines.
- Quality Engineer and Production Supervisor demo roles. The API enforces the Quality Engineer restriction on uploads, classification, and inspection creation; changing or hiding a frontend control is not the security boundary.
- Image upload (JPEG/PNG/WebP, 8 MB max), image verification, and local image storage.
- Product-agnostic vision classification through the OpenAI Responses API. Any product or household-object image can be submitted. The output is constrained to `Scratch`, `Dent`, `Paint Issue`, `Missing Component`, or `No Defect`. Unsupported defect labels fail closed to `No Defect` with a visible warning so a human must review the result; malformed provider output fails with a retryable API error.
- Separate `ai_classifications` and `inspections` records linked by a foreign key. The AI prediction, model, confidence, image reference and inspector are persisted when classification succeeds; the inspection stores the human final decision. `was_overridden` is derived server-side, not trusted from the browser. A classification can be submitted only once and only by the inspector who requested it.
- Filterable inspection list and dashboard KPIs. Defect rate = rejected / all inspections. AI acceptance rate = non-overridden / all inspections. Breakdown counts only rejected units by final defect category.
- Pytest coverage for taxonomy parsing and KPI calculations.

## Architecture

- `frontend/`: React + TypeScript + Vite single-page app.
- `backend/`: FastAPI API, SQLAlchemy persistence, OpenAI adapter and validation.
- `backend/app/ai_service.py`: isolates provider calls, accepts generic product images and constrains untrusted model output to the defect taxonomy.
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

Use Python 3.11 or newer when creating the environment. If `python3.11` is unavailable, install Python 3.11+ first or run the app with Docker Compose.

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
cp .env.example .env
npm run dev
```

Set the demo user ID in `frontend/.env`:

```env
VITE_DEFAULT_USER_ID=L040223
```

Use `L040223` for Priya Singh (Quality Engineer) or `L040224` for Alex Morgan (Production Supervisor). This ID selects a seeded demo profile; it is not a secret. Restart the Vite server after changing it.

Open http://localhost:5173.

### 3. Demo roles

The left navigation's settings icon switches between the seeded demo identities:
- Priya Singh — Quality Engineer (can upload/classify/submit inspections for any product image)
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

Install developer tools from `backend` when you need to run the checks:

```bash
cd backend
python -m pip install -r requirements-dev.txt
```

```bash
cd backend && python -m pytest -q
cd ../frontend && npm test
```

Checks:

```bash
cd backend && ruff format app tests && ruff check app tests && pip-audit -r requirements-dev.txt
cd ../frontend && npm run lint && npm audit --audit-level=high
```

Install the required pre-commit hook once from the repository root:

```bash
python -m pip install -r backend/requirements-dev.txt
pre-commit install
```

The `.pre-commit-config.yaml` hook runs backend tests, Ruff formatting and lint checks, `pip-audit`, frontend tests, ESLint and `npm audit` before each commit. Verify installation with `pre-commit run --all-files`. The hook intentionally fails if dependencies have not been installed or if a security audit reports a vulnerability at the configured severity.

## Vision model and cost

Provider: OpenAI. Default model: `gpt-4.1-mini`, configured through `OPENAI_MODEL`. It accepts image input and is a cost-conscious choice for a small prototype. The app makes one synchronous model request per classification; the timeout is 30 seconds and one SDK retry is enabled. Provider errors are returned as a safe `502` message, leaving the uploaded photo available for retry. Check the current model availability and pricing before running the exercise: https://platform.openai.com/docs/pricing and https://platform.openai.com/docs/guides/images-vision. Actual cost depends on image dimensions/detail and prompt/output tokens; record actual usage from the API usage dashboard rather than assuming a fixed per-image cost.

## Known limitations / deliberate shortcuts

- Demo role headers are not authentication. They demonstrate server-side authorization logic but must be replaced with signed/verified identity claims for production.
- Images are stored on the backend filesystem (a Docker volume in Compose), not object storage. A production system should use S3-compatible storage, signed URLs, retention controls and malware/content scanning.
- The model confidence is a self-reported estimate, not a calibrated probability. It is optional and displayed as such.
- Unsupported defect labels map to `No Defect` only as a safe taxonomy fallback, accompanied by a warning and mandatory human confirmation. Malformed model output is rejected for retry. A production workflow could add a separate `Needs review` state rather than conflating fallback with a clean result.
- The demo accepts any physical product image, including household objects. The model suggests visible defect categories only; it does not authenticate a product, SKU, model, material specification or batch from the photo. Production systems should use barcode/serial scanning and batch traceability wherever product identity matters.
- No batch CRUD, pagination, deletion, full authentication, production deployment, or background job queue is included (outside the core time-boxed scope). Classification is synchronous; the UI shows a loading state.
- SQLite is the default for quick setup. Use Compose for PostgreSQL. Schema creation is done with SQLAlchemy `create_all`; a production project should add Alembic migrations.

## Git setup

```bash
git init
git add .
git commit -m "Build AI-assisted quality inspection workflow"
```

A `.gitignore` excludes API secrets, local databases, uploads, virtual environments, build outputs and dependency folders.

## User identity and profile API

All business API requests identify the caller with the `X-User-Id` request header. The frontend no longer sends a user name or role; the backend resolves the user's name, role and permissions from its user directory.

```http
GET /api/users/me
X-User-Id: L040223
```

The response contains the complete demo profile used by the UI: `user_id`, `name`, `role`, `email`, `department`, `employee_type`, `permissions`, and `active`. The sidebar name and role are rendered from this response. Demo users are `L040223` (Priya Singh, Quality Engineer) and `L040224` (Alex Morgan, Production Supervisor). Unknown IDs are rejected with HTTP 401, and requests without the required header are rejected by FastAPI.

AI classifications and inspection records also retain the inspector's `user_id` so ownership checks do not depend on a display name. The included additive SQLite schema update adds this field to existing local demo databases. `GET /api/health` remains a public health probe.

> Demo note: `X-User-Id` is an identity lookup mechanism for this exercise, not authentication. A production deployment should derive the user ID from a verified login/session token and must not trust a caller-supplied header as proof of identity.
>>>>>>> Stashed changes
