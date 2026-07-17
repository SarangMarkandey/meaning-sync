# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync compares two people’s stated understanding of a verbal service agreement. It does not force agreement, provide legal advice, generate a legal contract, verify identity, or collect signatures. The repository includes a key-free deterministic demo and an English, same-device Live flow powered by OpenAI from FastAPI only.

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

`OPENAI_API_KEY` is optional for Demo Mode and required for Live agreement analysis or re-analysis. Check-understanding choices are constructed and validated deterministically by FastAPI; the normal choice path does not make an additional model request. Keep the key in `api/.env`; that file is ignored. The backend defaults to `OPENAI_MODEL=gpt-5.6`, forces `OPENAI_STORE_RESPONSES=false`, and uses a 30-second timeout. Configure explicit comma-separated frontend origins with `MEANINGSYNC_CORS_ORIGINS`. `MEANINGSYNC_CLARIFICATION_ATTEMPT_LIMIT=3` bounds repeated clarification for one agreement item.

In another terminal:

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. **Try Demo** starts the deterministic receipt flow. **Start Live Session** opens independent language setup and the English text workspace. Hindi is visible but disabled.

## Guided Live Workflow

Setup sits before the five-stage progress indicator. After both people choose English, Live Mode creates a server-owned session and follows:

`Conversation → Clarify → Check understanding → Confirm → Receipt`

**Analyzing** is a dedicated, non-clickable state while MeaningSync moves from Conversation to Clarify or Check understanding. The page shows one server-selected next action instead of asking users to interpret the lifecycle. Required issues are handled in a consistent order—scope, amount and price coverage, materials, timing, payment, then other critical responsibilities. A required issue may be resolved or carried forward only through an explicit **Continue unresolved** choice. Topics that were simply not discussed appear later as optional details and can be handled together rather than blocking the main path.

Clarification and Check understanding use neutral, tap-based options derived from recorded participant positions or shared meaning. Every question includes **Something else** and **I'm not sure**; free text is required only after **Something else** is selected. MeaningSync removes semantic duplicates and never repeats an item already independently answered during clarification. After a completed two-party clarification, it asks at most one additional high-impact question; if none remains, it proceeds directly to separate confirmation. Without clarification, a simple agreement normally receives one or two questions and a broad agreement receives at most three.

The interface uses progressive disclosure: plain-language summaries and the next action appear first; original evidence, technical item keys, previous maps, and optional details stay available on demand. Same-device handoffs separate Homeowner and Electrician selections and confirmations. The first selection is withheld until the second participant submits, but this presentation boundary does not provide authentication or strong privacy.

Every analysis remains an immutable internal event. The user-facing Agreement Map version advances only when a deterministic semantic fingerprint shows a meaningful state or participant-position change, so retries, formatting differences, or neutral-summary wording alone do not create a noisy “new version.” Agreement versions, questions, private selections, clarification messages, confirmations, and the receipt are stored only in the FastAPI process. Refresh can recover while that process is still running; a restart loses the session and the UI reports that limitation truthfully.

## How MeaningSync was built with Codex and GPT-5.6

Codex helped inspect the repository architecture, implement the FastAPI and Next.js workflow, add regression tests, and iterate on UI usability. The builder made the core product decisions: start with same-language conversations, preserve original evidence, clarify exact meanings, use choice-based understanding checks, state the same-device privacy boundary honestly, and position the output as a clarity receipt rather than a legal contract.

GPT-5.6 is the final hackathon model and performs the core English agreement analysis through the Responses API with Pydantic Structured Outputs and `store=False`. The `OPENAI_MODEL` environment setting remains available for local experiments, but the committed default is `gpt-5.6`. Clarification choices, semantic question deduplication, workflow transitions, and receipt generation are controlled by application code and do not trigger additional model calls.

## Current Limitations

Live sessions are English text only and use a same-device handoff. Storage is process-local, so a backend restart loses the session. There is no authentication or role-bound participant token, QR joining, separate-device flow, or realtime synchronization.

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

Implemented: deterministic English demo; the guided five-stage English Live flow; server-derived next-action guidance; required-versus-optional issue handling; immutable internal agreement events with meaningful user-facing versions; exact choice-based clarification; bounded, deduplicated understanding checks; same-device independent selections; version-bound confirmations; and an immutable clarity-receipt snapshot with unresolved-item categories and an integrity hash.

Partially implemented: language-neutral data structures, same-device privacy cues, and optional-detail batching within one session. Planned: validated usability research beyond the current first-click criteria, Hindi/translation, audio and recording consent, QR/separate-device joining, authentication, durable persistence and recovery, retention controls, custom PDF generation, and identity or signature verification. MeaningSync records independent selections and makes differences visible; it does not prove comprehension, identity, consent, or legal enforceability.
