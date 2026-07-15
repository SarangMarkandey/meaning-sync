# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync helps two people compare their understanding of a verbal service agreement. Milestone 1 is a deterministic demo using a prepared Hindi–English electrician conversation. It does not record audio, call OpenAI, or create a legal contract.

## Prerequisites

- Node.js 20+ and npm
- Python 3.12+

## Run the API

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload --env-file .env
```

The API runs at `http://localhost:8000`; verify it with `GET /health`.

## Run the web app

In a second terminal:

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000` and select **Try Demo**. Live Mode is intentionally disabled for this milestone.

## Verification

```bash
cd api
ruff check .
ruff format --check .
pytest

cd ../web
npm run lint
npm run type-check
npm test
npm run build
```

Session data is stored only in API process memory and disappears on restart. Configure allowed frontend origins with the comma-separated `MEANINGSYNC_CORS_ORIGINS`; wildcard origins are rejected.
