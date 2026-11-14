#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
python -m pytest -q
ruff check app tests
ruff format app tests
pip-audit -r requirements.txt
cd "$ROOT/frontend"
npm test
npm run lint
npm audit --audit-level=high
