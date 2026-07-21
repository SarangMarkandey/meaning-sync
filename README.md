# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync compares what two people understood from a spoken or typed service conversation, shows what matches, differs, or remains open, and creates a clarity receipt confirmed separately by both people. It is not a legal contract, signature, payment, or identity-verification product.

## Judge quick start — no API key required

MeaningSync is provided as a judge-ready local test build. No login, test credentials, or OpenAI API key is required for the deterministic demos. Use the `v1.0.0-build-week` submission tag for the frozen judging build, or `main` for the submitted branch.

Prerequisites: Python 3.12+, [uv 0.6+](https://docs.astral.sh/uv/getting-started/installation/), Node.js 20+, and npm.

From the repository root, install dependencies once:

```bash
cd api
uv sync --locked --extra dev
cd ../web
npm ci
cd ..
```

Start the isolated Demo build:

```bash
./scripts/run-demo.sh
```

Open the local URL printed by the script and select **English / Hindi Demo** for the recommended judge path. Press `Ctrl+C` when finished; the script stops both servers and removes its temporary SQLite database.

The available deterministic paths are:

- **English Demo** for the prepared English conversation.
- **English / Hindi Demo** for a Hindi-speaking Homeowner and English-speaking Electrician.

Both demos require no PostgreSQL, Docker, microphone, account, or paid API request. They preserve original evidence, show deterministic translations, surface the replacement-parts conflict, hide the first private choice, require two separate confirmations, and retain open items in a bilingual clarity receipt.

See the complete [Judge Test Guide](docs/judge-test-guide.md).

## Live Mode

Live Mode supports:

- English/English, Hindi/Hindi, and either mixed-language direction
- Typed messages or reviewed audio transcripts
- INR, USD, or EUR metadata
- One shared device or separate devices joined through a single-use QR code or link

Optional display names are self-provided and role-scoped. They do not verify anyone’s identity.

The long-lived OpenAI project key is configured only in `api/.env` and is never exposed to browser code. Responses API analysis and translation run through FastAPI. Live audio uses a backend-issued, short-lived Realtime credential for the browser WebRTC session.

Add a personal project key to `api/.env` to use Live agreement analysis, mixed-language translation, or Realtime transcription. GPT-5.6 performs the agreement reasoning through Responses API Structured Outputs. The backend sets `store=false`. Microphone access requires HTTPS or the browser’s `http://localhost` exception. MeaningSync stores finalized, reviewed transcripts and correction provenance—never raw audio.

Live data defaults to the ignored local SQLite database at `api/meaningsync-local.db`. Before starting Live Mode, apply the database migrations:

```bash
cd api
uv run alembic upgrade head
```

Sessions, role-bound credential hashes, single-use invitation hashes, translations, immutable agreement versions, private choices, confirmations, and receipts survive backend restarts until expiry. Synchronization currently uses bounded polling.

For complete configuration and startup instructions, see the [Judge Test Guide](docs/judge-test-guide.md).

## Product flow and safety

`Preferences → Participation → Conversation → Check understanding → Confirm → Receipt`

Original words remain immutable evidence. Derived translations have `pending`, `ready`, or `failed` status and never replace the original or become evidence themselves. Agreement and choice comparisons use stable semantic IDs rather than translated strings.

If translation fails, the original statement remains visible and the translation is retryable. Each participant confirms the same agreement-version ID in their chosen language. Mixed-language receipts include English and Hindi term views, original evidence, confirmation bindings, unresolved status, and an integrity hash.

### Current limitations

- English and Hindi only
- Translations are useful views but are not guaranteed to be perfect
- Access credentials authorize an application role but do not verify a person
- No accounts, signatures, legal enforceability, automatic deletion UI, or participant audio call
- Separate-device synchronization uses polling rather than full realtime updates

## Verification

Run the complete submission verification from the repository root:

```bash
./scripts/verify-submission.sh
```

Or run the checks individually:

```bash
cd api
uv run ruff format --check .
uv run ruff check .
uv run pytest

cd ../web
npm run lint
npm run type-check
npm test
npm run build
```

Normal tests use deterministic or fake services and spend no API credits. Paid analysis and transcription tests are opt-in and skipped by default.

## How MeaningSync was built with Codex and GPT-5.6

Codex helped me audit the architecture, implement FastAPI and Next.js changes, build deterministic fixtures, expand regression tests, and iterate on the guided interface for non-technical users.

I made the core product decisions: preserve original words, keep private answers hidden, avoid inferred confirmation, support shared and separate devices, and call the output a clarity receipt rather than a contract. I used Codex to redesign the earlier questionnaire-like experience into one conversation-first, six-step flow.

GPT-5.6 performs language-independent agreement reasoning through backend-only Responses API Structured Outputs. OpenAI Structured Outputs also support meaning-preserving Live translation through the backend. Realtime transcription supplies a reviewed original-evidence record; it does not produce an AI voice response.

The deterministic English and bilingual Demo modes mirror the important product flow without an API key, microphone, or paid request, allowing judges to evaluate MeaningSync reliably.

A detailed milestone-by-milestone record of the Codex collaboration and major product decisions is available in [BUILD_LOG.md](BUILD_LOG.md).