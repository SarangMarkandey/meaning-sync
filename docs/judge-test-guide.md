# Judge Test Guide

MeaningSync is provided as a judge-ready local test build. The deterministic
English and Hindi–English demos require no login, test credentials, OpenAI API
key, PostgreSQL, Docker, microphone, or paid API request.

## Recommended no-key setup

Test `main` or the `v1.0.0-build-week` submission tag when it is available.
MeaningSync is tested locally on Ubuntu/Linux with Python 3.12+, uv 0.6+,
Node.js 20+, and npm.

From a fresh clone:

```bash
git checkout main
# Alternatively, after the release tag is published:
# git checkout v1.0.0-build-week

cd api
uv sync --locked --extra dev
cd ../web
npm ci
cd ..
./scripts/run-demo.sh
```

The script creates a temporary SQLite database, applies migrations, starts the
backend and frontend, and prints the local Demo URL. Open that URL and press
`Ctrl+C` when finished. No `.env` file is required for this path.

## Recommended Hindi–English evaluation

1. Select **English / Hindi Demo**.
2. Complete each participant's consent separately.
3. Review the Hindi Homeowner and English Electrician conversation.
4. Verify that original evidence remains visible alongside deterministic translated views.
5. Compare understanding: scope, ₹1,200 labour, and today's start match; replacement-parts inclusion needs a decision.
6. Submit each participant's private materials choice and verify that the first response remains hidden until the second is submitted.
7. Complete each participant's confirmation separately.
8. Create the bilingual clarity receipt and verify that unresolved and not-discussed items remain visible.

## English Demo

1. Open the URL printed by `scripts/run-demo.sh`.
2. Choose **English Demo**, consent separately, and review the prepared evidence.
3. Compare understanding. Confirm scope, ₹1,200 labour, and today’s start; observe that replacement-parts inclusion conflicts.
4. Submit each private materials choice. Verify the first stays hidden.
5. Confirm separately and create the receipt. Payment timing, completion, warranty, cancellation, responsibilities, and additional-work policy remain open.

## Live text and audio

Live text requires a user-provided `OPENAI_API_KEY` for GPT-5.6 analysis and mixed-language translation. Same-language message entry itself does not call OpenAI. Test all four English/Hindi combinations and either shared-device private handoffs or the single-use separate-device QR/link.

Live audio additionally requires microphone permission and network access to OpenAI Realtime. Use HTTPS or `http://localhost`; ordinary LAN HTTP is not a secure microphone context. Review/correct the finalized transcript before adding it. MeaningSync stores no raw audio.

## Troubleshooting and limitations

- Backend health: `curl http://localhost:8000/health`.
- If port 3000 or 8000 is already in use, stop the existing development server before running the Demo script.
- If startup reports an unmigrated database, run `cd api && uv run alembic upgrade head`.
- If the UI cannot reach FastAPI, verify `web/.env.local` and explicit backend CORS origins.
- A failed translation leaves original evidence visible; use **Retry translation**.
- MeaningSync supports English and Hindi only. Translation is not guaranteed perfect, names are not verified, polling is used instead of WebSockets, and the receipt is not a legally enforceable contract.

## Submission version

`v1.0.0-build-week`
