# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync compares two people’s stated understanding of a verbal service agreement. It is not a legal-contract generator and does not provide legal advice. The repository currently includes a key-free deterministic demo and an English text-based live-analysis preview powered by OpenAI from FastAPI only.

## Local Setup

Prerequisites are Node.js 20+, npm, and Python 3.12+.

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`OPENAI_API_KEY` is optional for Demo Mode and required only for Live Text Analysis. Keep it in `api/.env`; that file is ignored. The backend defaults to `OPENAI_MODEL=gpt-5.6`, forces `OPENAI_STORE_RESPONSES=false`, and uses a 30-second timeout. Configure explicit comma-separated frontend origins with `MEANINGSYNC_CORS_ORIGINS`.

In another terminal:

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. **Try Demo** starts the deterministic receipt flow. **Start Live Session** opens independent language setup and the English text workspace. Hindi is visible but disabled.

## Verification

```bash
cd api
ruff format --check .
ruff check .
pytest
python -c "from app.main import app; print(app.title)"

cd ../web
npm run lint
npm run type-check
npm test
npm run build
```

Normal tests mock OpenAI and spend no credits. `RUN_OPENAI_INTEGRATION=1 pytest tests/test_evaluations.py` is an explicit paid evaluation and is skipped by default.

## Status

Implemented: deterministic English demo, in-memory sessions, English live text entry, backend Structured Outputs, evidence validation, and safe errors. Partially implemented: language-neutral data structures. Planned: audio and consent for audio, Hindi/translation, QR joining, persistence, separate live confirmations, and a live clarity receipt.
