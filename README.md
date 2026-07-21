# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync helps a customer and a service provider compare what each person understood from a spoken or typed conversation. It shows what matches, what needs a decision, and what was never discussed, then creates a clarity receipt that both people confirm separately.

It is designed for everyday service work such as repairs, freelance projects, home services, and other informal agreements. A MeaningSync receipt is not a legal contract, signature, payment record, or proof of identity.

## What it does

- Preserves each participant's original English or Hindi words as evidence
- Supports typed messages and reviewed audio transcripts
- Compares matching terms, differences, one-sided statements, and missing topics
- Keeps the first participant's private choice hidden until both people answer
- Supports shared-device and separate-device sessions
- Creates role-bound, expiring, single-use invitation links and QR codes
- Requires each participant to confirm the same agreement version separately
- Produces a bilingual clarity receipt with unresolved items and an integrity hash
- Includes deterministic English and English/Hindi demos that use no API credits

## Product flow

`Preferences → Participation → Conversation → Check understanding → Confirm → Receipt`

MeaningSync never treats silence as agreement. Original statements remain unchanged, translations are shown only as derived views, and unresolved points stay visible on the final receipt.

## Tech stack

- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS, and Vitest
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic, and Pytest
- **Database:** SQLite by default; PostgreSQL is also supported
- **AI:** OpenAI Responses API Structured Outputs with GPT-5.6
- **Audio:** OpenAI Realtime transcription over WebRTC

## Requirements

Install these before starting:

- Git
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.6 or newer
- Node.js 20 or newer
- npm

Docker and PostgreSQL are not required for local development.

## Quick start: Demo Mode

Demo Mode is the fastest way to run the complete product flow. It uses prepared data and does not require an OpenAI API key, microphone, account, Docker, or PostgreSQL.

```bash
git clone https://github.com/SarangMarkandey/meaning-sync.git
cd meaning-sync

cd api
uv sync --locked --extra dev

cd ../web
npm ci

cd ..
./scripts/run-demo.sh
```

Open the URL printed by the script, normally:

```text
http://localhost:3000/demo/setup
```

Choose **English Demo** or **English / Hindi Demo** and follow the six guided steps. Press `Ctrl+C` when finished. The script stops both servers and removes the temporary Demo database.

## Full local installation

Use this setup when you want to run Demo Mode and Live Mode from the same local project.

### 1. Clone the repository

```bash
git clone https://github.com/SarangMarkandey/meaning-sync.git
cd meaning-sync
```

If the repository is private, GitHub will ask you to authenticate with an account that has access.

### 2. Install the backend

```bash
cd api
uv sync --locked --extra dev
cp .env.example .env
```

Open `api/.env` and add your OpenAI project key:

```dotenv
OPENAI_API_KEY=your_openai_project_key
OPENAI_MODEL=gpt-5.6
OPENAI_TRANSLATION_MODEL=gpt-5.6
OPENAI_STORE_RESPONSES=false
```

The key is required for Live agreement analysis, mixed-language translation, and audio transcription. Keep `OPENAI_STORE_RESPONSES=false` and never commit `api/.env`.

The default local configuration uses:

```dotenv
MEANINGSYNC_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
MEANINGSYNC_DATABASE_URL=sqlite:///./meaningsync-local.db
```

Most local users do not need to change the other backend settings in `.env.example`.

### 3. Install the frontend

```bash
cd ../web
npm ci
cp .env.example .env.local
```

The default `web/.env.local` values are:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MEANINGSYNC_APP_URL=http://localhost:3000
NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS=1500
```

Do not put `OPENAI_API_KEY` or any other secret in `web/.env.local`. Variables prefixed with `NEXT_PUBLIC_` are available to browser code.

### 4. Initialize the database

```bash
cd ../api
uv run alembic upgrade head
```

This creates `api/meaningsync-local.db`. The file is local runtime data and is ignored by Git.

### 5. Start the backend and frontend

Run the backend in one terminal:

```bash
cd api
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the frontend in a second terminal:

```bash
cd web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

To confirm that the backend is ready:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

FastAPI's local API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Using MeaningSync

### Demo Mode

Select **Try the demo**, choose an English or English/Hindi preset, and follow the prepared conversation. Demo Mode is deterministic: it does not call OpenAI and is safe to repeat while testing the UI.

### Live Mode

1. Select a language for the Customer and Service provider.
2. Choose INR, USD, or EUR. MeaningSync records the currency but does not convert amounts.
3. Choose your role and enter an optional display name.
4. Choose whether both people will share one device or use separate devices.
5. Type messages or add a reviewed audio transcript.
6. After both people have contributed, each person marks themselves ready.
7. The session creator selects **Compare what we mean**.
8. Review matches, decisions needed, and topics that were not discussed.
9. Complete any private choices, then confirm separately as each participant.
10. Create the clarity receipt.

In shared-device mode, pass the screen between participants when prompted. To test separate-device mode on one computer, open the invitation in another browser profile or an incognito window so each role has separate session storage.

### Audio transcription

Audio input requires microphone permission and access to OpenAI Realtime. `http://localhost` works for local development; testing from another physical device requires HTTPS because browsers restrict microphone access on ordinary LAN HTTP pages.

The browser sends an authorized WebRTC SDP offer to FastAPI. FastAPI initializes the transcription-only Realtime call with the server-side OpenAI key and returns only the SDP answer. Participants review or correct the final transcript before adding it to the conversation. MeaningSync does not persist raw audio, SDP, or partial transcript events.

## Data and security boundaries

- The OpenAI project key stays in the backend environment.
- Responses API analysis and translation use Structured Outputs with `store=false`.
- Original statements remain the evidence; translations never replace them.
- Live sessions, credential hashes, invitation hashes, translations, choices, confirmations, and receipts are stored until configured expiry.
- Role credentials authorize a participant role but do not verify a person's identity.
- The receipt integrity hash can reveal payload changes, but it is not a signature or trusted timestamp.
- Automatic expired-data cleanup, user-facing deletion, and backup management are not implemented yet.

See [Privacy and Safety](docs/privacy-and-safety.md) for the complete boundary.

## Testing and verification

Run the deterministic submission checks from the repository root:

```bash
./scripts/verify-submission.sh
```

Run the complete backend checks:

```bash
cd api
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Run the complete frontend checks:

```bash
cd web
npm run lint
npm run type-check
npm test
npm run build
```

Normal tests use deterministic or fake services and spend no OpenAI credits. Paid integration tests are opt-in and skipped by default.

## Project structure

```text
meaning-sync/
├── api/                 FastAPI application, database migrations, and tests
│   ├── alembic/         SQL schema migrations
│   ├── app/             API routes, domain models, repositories, and services
│   └── tests/           Backend and integration tests
├── web/                 Next.js application and component tests
│   ├── public/          Static assets
│   └── src/             Routes, components, and browser API client
├── docs/                Product, architecture, API, and safety documentation
├── scripts/             Demo startup and verification scripts
└── BUILD_LOG.md         Milestone history and major implementation decisions
```

## OpenAI Build Week: Codex and GPT-5.6

I built MeaningSync with Codex as my implementation partner. Codex helped me audit the architecture, implement and review the FastAPI and Next.js flows, design deterministic fixtures, expand regression tests, and simplify an earlier questionnaire-style experience into the current six-step conversation flow.

I made the product decisions behind the safety model: preserve original words, hide the first private answer, never infer confirmation, support shared and separate devices, and call the result a clarity receipt rather than a contract. The milestone history is recorded in [BUILD_LOG.md](BUILD_LOG.md).

GPT-5.6 powers Live agreement reasoning and meaning-preserving translation through backend-only Responses API Structured Outputs. The product uses stable semantic IDs and validates model output against trusted participant evidence before showing a result. OpenAI Realtime provides reviewed transcription; it is not used to generate an AI voice response.

The deterministic Demo modes mirror the important experience without an API key or paid request so the product can be tested reliably.

Build Week judges can follow the dedicated [Judge Test Guide](docs/judge-test-guide.md) and use the `v1.0.0-build-week` tag for the frozen submission build.

## Current limitations

- English and Hindi only
- Machine translations may be imperfect
- Polling instead of WebSockets for separate-device synchronization
- No accounts, identity verification, signatures, payments, or legal enforceability
- No participant-to-participant audio call
- No automatic cleanup job or user-facing deletion controls
