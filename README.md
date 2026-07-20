# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync compares two people’s stated understanding of a verbal service agreement. It does not force agreement, provide legal advice, generate a legal contract, verify identity, or collect signatures. The repository includes a key-free deterministic demo and English Live flows for a shared device or two separately authorized devices. Only FastAPI can call OpenAI.

## Local Setup

Prerequisites are Node.js 20+, npm, Python 3.12+, and [uv](https://docs.astral.sh/uv/).

```bash
cd api
uv sync --locked --extra dev
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`OPENAI_API_KEY` is optional for Demo Mode and required for Live agreement analysis, re-analysis, and microphone transcription. Check-understanding choices are constructed and validated deterministically by FastAPI; the normal choice path does not make an additional model request. Keep the key in `api/.env`; that file is ignored. The backend defaults to `OPENAI_MODEL=gpt-5.6`, forces `OPENAI_STORE_RESPONSES=false`, and uses a 30-second timeout. Configure explicit comma-separated frontend origins with `MEANINGSYNC_CORS_ORIGINS`. `MEANINGSYNC_CLARIFICATION_ATTEMPT_LIMIT=3` bounds repeated clarification for one agreement item.

Audio defaults to `OPENAI_TRANSCRIPTION_MODEL=gpt-realtime-whisper`, a 60-second turn, 600 seconds per participant/session, 12-second initialization timeout, 20-second finalization idle timeout, 2,000-character finalized transcript, and one overlapping initializer per role. All are documented in `api/.env.example`. Browser microphones require HTTPS or the `http://localhost` development exception; a plain LAN IP may be rejected.

Live sessions use `MEANINGSYNC_DATABASE_URL`; local development defaults to the ignored `api/meaningsync-local.db` SQLite file. Run `uv run alembic upgrade head` before starting FastAPI. Production should use a backend-only PostgreSQL URL such as `postgresql+psycopg://...`, never a `NEXT_PUBLIC_*` variable. `MEANINGSYNC_SESSION_TTL_HOURS=24`, `MEANINGSYNC_ACCESS_TOKEN_TTL_HOURS=24`, and `MEANINGSYNC_INVITE_TTL_MINUTES=15` independently bound session, credential, and invitation lifetime. Raw secrets are never stored in SQL.

In another terminal:

```bash
cd web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. **Try Demo** starts the deterministic receipt flow. **Start Live Session** opens independent language setup and the English text workspace. Hindi is visible but disabled.

For separate-device testing on an Ubuntu LAN, set the reachable host address in both env files:

```dotenv
# api/.env
MEANINGSYNC_CORS_ORIGINS=http://192.168.1.50:3000

# web/.env.local
NEXT_PUBLIC_API_URL=http://192.168.1.50:8000
NEXT_PUBLIC_MEANINGSYNC_APP_URL=http://192.168.1.50:3000
NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS=1500
```

Start Uvicorn with `--host 0.0.0.0` and Next.js with `npm run dev -- --hostname 0.0.0.0`. Allow only ports 3000 and 8000 on the trusted LAN; do not expose this development setup directly to the public internet.

## Conversation-first Workflow

Demo and Live use the same six visible steps:

`Preferences → Participation → Conversation → Check understanding → Confirm → Receipt`

Preferences choose each person’s language and the session currency. Demo is the prepared English/INR scenario; Live supports English plus INR, USD, or EUR. Currency is metadata only: original evidence keeps the amount and currency stated by a participant, and MeaningSync does not convert values. Participation chooses **Customer** or **Service provider** as the creator role and a shared- or separate-device path. Separate-device sessions issue a role-bound credential to the creator and a single-use invitation to the opposite role. The join screen removes its fragment secret, exchanges it after the invited person accepts the notice, and both devices move to Conversation automatically.

Conversation is a role-scoped Type/Speak workspace, not a form, call, or chatbot. Typed text remains available throughout. Speak requires participant-specific, versioned consent before microphone access. The browser uses transcription-only WebRTC initialized by FastAPI; MeaningSync stores only a reviewed finalized transcript and correction provenance, never raw audio, SDP, partial deltas, or credentials. Text and audio transcripts share one chronological ledger. A new message clears both readiness flags and current confirmations. Only the session creator can compare after both people have spoken and are ready.

Check understanding shows one agreement map with **Matches**, **Needs a decision**, and **Not discussed** sections. Every non-missing item links to original evidence. Matching items require no extra controls. Conflicting or one-sided items use private, neutral choices; the first choice stays hidden until the other addressed person answers. Compatible choices can create a new immutable agreement version. Different choices remain unresolved and are not asked again until the people deliberately return to Conversation. Not-discussed topics are optional and never block confirmation.

Confirmation is separate for each participant and binds the same current version. Requesting a change returns to Conversation, identifies the item to revisit, and invalidates old readiness and confirmations. The final clarity receipt preserves matching, unresolved, one-sided, and not-discussed items; roles, languages, session currency, original evidence currency, timestamps, agreement history, and an integrity hash. It is not a legal contract.

Every analysis remains an immutable internal event. The user-facing Agreement Map version advances only when a deterministic semantic fingerprint shows a meaningful state or participant-position change, so retries, formatting differences, or neutral-summary wording alone do not create a noisy “new version.” Agreement versions, questions, private selections, clarification messages, confirmations, idempotency records, and receipts are stored as validated versioned JSON through the Live repository. They survive a backend restart until expiry. Demo Mode remains process-local.

## How MeaningSync was built with Codex and GPT-5.6

Codex helped inspect the repository architecture, implement the FastAPI and Next.js workflow, add regression tests, and iterate on UI usability. The builder made the core product decisions: start with same-language conversations, preserve original evidence, clarify exact meanings, use choice-based understanding checks, state shared- and separate-device security boundaries honestly, and position the output as a clarity receipt rather than a legal contract.

GPT-5.6 is the final hackathon model and performs the core English agreement analysis through the Responses API with Pydantic Structured Outputs and `store=False`. The `OPENAI_MODEL` environment setting remains available for local experiments, but the committed default is `gpt-5.6`. Clarification choices, semantic question deduplication, workflow transitions, and receipt generation are controlled by application code and do not trigger additional model calls.

## Current Limitations

Live sessions are English only; Conversation accepts typed text or reviewed audio transcripts. P1B credentials authorize one role in one session but do not verify identity. Synchronization uses bounded polling. There is no translation, diarization, participant audio call, AI voice response, user account, automatic cleanup, user-facing deletion, electronic signature, or legal-contract status. Microphone access requires HTTPS or `http://localhost`; ordinary LAN HTTP may be rejected by browsers.

## Verification

```bash
cd api
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run python -c "from app.main import app; print(app.title)"

cd ../web
npm run lint
npm run type-check
npm test
npm run build
```

Normal tests mock OpenAI and spend no credits. `RUN_OPENAI_INTEGRATION=1 pytest tests/test_evaluations.py` is an explicit paid evaluation and is skipped by default.
The Realtime initializer harness is also disabled by default; it requires `RUN_OPENAI_TRANSCRIPTION_INTEGRATION=1` plus an authorized key and a valid `OPENAI_REALTIME_TEST_SDP` offer. Do not enable either paid gate during routine verification.

## Status

Implemented: deterministic English/INR demo; the six-step conversation-first Live flow on shared or separate devices; consent-gated transcription-only WebRTC with review/correction and typed fallback; creator-selectable Customer/Service provider roles; INR/USD/EUR session metadata; readiness-gated comparison; local QR joining; single-use invitations; role-bound bearer authorization; revision-aware polling and presence; choice-based decisions; version-bound confirmations; immutable receipts; and durable SQL-backed sessions with restart recovery, optimistic revisions, expiry, and persistent idempotency.

Partially implemented: language-neutral data structures, role authorization without identity verification, optional-detail batching, and time-based retention without automatic cleanup or deletion tooling. Planned: validated usability research, Hindi/translation, backup/deletion operations, and privacy-preserving observability. MeaningSync records independent selections and makes differences visible; it does not prove comprehension, identity, consent, or legal enforceability.
