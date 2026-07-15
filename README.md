# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync helps two people determine whether they understand a service agreement in the same way. It supports same-language and, in future milestones, cross-language conversations; translation is optional support, not the product. The current deterministic demo is English ↔ English and makes no OpenAI or audio calls. MeaningSync does not provide legal advice or create a legally enforceable contract.

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
fastapi dev
```

The configured FastAPI entrypoint is `app.main:app`. Equivalent explicit development command:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For a production-style local run without reload:

```bash
fastapi run --host 0.0.0.0 --port 8000
```

Do not configure multiple workers yet: sessions live only in one process’s memory, so workers would hold inconsistent session state. The API runs at `http://localhost:8000`; verify it with `GET /health`.

## Run the web app

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000` and select **Try Demo**. The homepage then navigates to `/demo/setup`, where the homeowner and electrician have separate language controls that both default to English. **Start Demo** carries those values in the `/demo` URL and into session creation. Hindi-only, mixed-language, and Live Mode experiences are visibly planned but not implemented.

The implemented user flow is:

`Homepage → Demo language setup → Demo conversation → Agreement map → Clarification → Separate confirmations → Clarity receipt`

Language selectors and implementation-status messaging intentionally appear only on the setup screen, not the public homepage.

## Verification

```bash
cd api
ruff check .
ruff format --check .
pytest
python -c "from app.main import app; print(app.title)"

cd ../web
npm run lint
npm run type-check
npm test
npm run build
```

Configure allowed frontend origins with comma-separated `MEANINGSYNC_CORS_ORIGINS`; wildcard origins are rejected. See [docs/](docs/) for product, language, architecture, API, and roadmap details.
