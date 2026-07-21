# MeaningSync

> Make sure both sides mean the same thing.

MeaningSync compares two people’s spoken or typed service agreement, shows what matches, differs, or remains open, and creates a clarity receipt confirmed separately by both people. It is not a legal-contract, signature, payment, or identity-verification product.

## Judge quick start — no API key required

MeaningSync is provided as a judge-ready local test build. No login, test
credentials, or OpenAI API key is required for the deterministic demos. Use
`main` or the `v1.0.0-build-week` submission tag when it is available.

Prerequisites: Python 3.12+, [uv 0.6+](https://docs.astral.sh/uv/getting-started/installation/), Node.js 20+, and npm. From the repository root, install dependencies once:

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

Both demos require no PostgreSQL, Docker, microphone, account, or paid API request. They preserve original evidence, show deterministic translations, surface the replacement-parts conflict, hide the first private choice, require two separate confirmations, and retain open items in a bilingual clarity receipt. See the complete [Judge Test Guide](docs/judge-test-guide.md).

## Live Mode

Live supports English/English, Hindi/Hindi, and either mixed direction; text or reviewed audio transcripts; INR, USD, or EUR metadata; and one shared device or separate devices joined with a single-use QR/link. Optional display names are self-provided, role-scoped, and never identity verification.

Only FastAPI calls OpenAI. Add a personal project key to `api/.env` to use Live GPT-5.6 agreement analysis, mixed-language translation, or Realtime transcription. The backend uses Responses API Structured Outputs with `store=false`; browser code never receives the key. Microphone access requires HTTPS or the browser’s `http://localhost` exception. MeaningSync stores finalized reviewed transcripts and correction provenance, never raw audio.

Live data defaults to ignored local SQLite at `api/meaningsync-local.db`. Run `uv run alembic upgrade head` before startup. Sessions, role-bound credential hashes, single-use invitation hashes, translations, immutable agreement versions, private choices, confirmations, and receipts survive restart until expiry. Synchronization uses bounded polling.

## Product Flow and Safety

`Preferences → Participation → Conversation → Check understanding → Confirm → Receipt`

Original words are immutable evidence. Derived translations have `pending`, `ready`, or `failed` status and never replace or become evidence. Agreement and choice comparisons use stable semantic IDs, not translated strings. A translation failure leaves the original visible and retryable. Each participant confirms the same agreement-version ID in their chosen language. Mixed-language receipts include English and Hindi term views, original evidence, confirmation bindings, unresolved status, and an integrity hash.

Current limitations: English and Hindi only; translations are useful views, not guaranteed perfect; access credentials authorize a role but do not verify a person; no accounts, signatures, legal enforceability, automatic deletion UI, or participant audio call.

## Verification

```bash
./scripts/verify-submission.sh

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

Normal tests use deterministic/fake services and spend no credits. Paid analysis/transcription tests are opt-in and skipped by default.

## How MeaningSync was built with Codex and GPT-5.6

Codex helped the builder audit the architecture, implement FastAPI and Next.js changes, build deterministic fixtures, expand regression tests, and iterate on the guided non-technical UI. The builder made the product decisions: preserve original words, keep private answers hidden, avoid inferred confirmation, support same/separate devices, and call the output a clarity receipt rather than a contract. The earlier questionnaire-like experience was redesigned with Codex into one conversation-first six-step flow.

GPT-5.6 performs language-independent agreement reasoning and meaning-preserving Live translation through backend-only Structured Outputs. Realtime transcription supplies a reviewed original-evidence record; it does not produce an AI voice response. Deterministic English and bilingual Demo modes mirror the important flow without an API key, microphone, or paid request so judges can evaluate the product reliably.
