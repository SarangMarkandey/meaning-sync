# Build Log

## Milestone 1 — Deterministic Demo Mode

**Date:** 2026-07-14

- Added a FastAPI application with explicit CORS configuration, health check, typed session models, and in-memory storage.
- Implemented the ordered session lifecycle from creation through consent, evidence analysis, private clarification, two-party teach-back confirmation, and clarity receipt.
- Added the prepared Hindi–English electrician scenario with transcript evidence for every non-missing term.
- Built a mobile-first Next.js demo with consent, evidence, agreement-map, clarification, and receipt screens plus loading, error, and empty states.
- Added backend state/privacy tests and focused frontend agreement-map rendering tests.
- Documented local setup, architecture boundaries, environment variables, and repository conventions.

Milestone 1 intentionally contains no OpenAI calls, audio recording, authentication, persistence, QR joining, or deployment configuration.

## Milestone 2 — English-first Agreement Intelligence

**Date:** 2026-07-15

- Replaced the Hindi/Hinglish fixture with the specified English homeowner–electrician conversation and an English-first nine-term agreement map.
- Added independent `en`/`hi` participant language settings while keeping English as both defaults.
- Expanded messages and evidence with session, participant, original-language, original-text, timestamp, translation, and per-participant term provenance.
- Added a minimal optional translation-service boundary; same-language sessions bypass it.
- Changed clarification matching to canonical materials meaning instead of exact answer strings.
- Updated the frontend language controls, original-evidence display, materials conflict, tests, local commands, and product documentation.

Implemented now: deterministic English ↔ English Demo Mode. Partially implemented: language-neutral data structures and translation boundary. Planned: Hindi flows, real translation, OpenAI extraction, audio, separate devices, persistence, and Live Mode.

## Focused UX Correction — Demo Language Setup

**Date:** 2026-07-15

- Removed participant-language controls and implementation-status copy from the homepage without changing its visual structure.
- Added `/demo/setup` with separate, accessible homeowner and electrician language controls, English defaults, an English ↔ English summary, and Back/Start actions.
- Added `/demo`, which validates `hirer_language` and `worker_language` URL parameters before passing them to the existing typed demo-session request.
- Kept Hindi visible as coming soon and disabled; unsupported query combinations redirect to setup. Live Mode remains disabled.
- Preserved the English transcript, replacement-parts conflict, agreement map, original evidence, private clarification, separate confirmation, and clarity receipt.

Verification results:

- `ruff check` and `ruff format --check` on milestone backend files: passed.
- `pytest -q`: 14 passed.
- `npm run lint`: passed.
- `npm run type-check`: passed.
- `npm test`: 11 passed.
- `npm run build`: passed.
- FastAPI import/OpenAPI and development-server startup: passed.

The whole-tree Ruff check still reports the preserved pre-existing whitespace edit in `api/app/config.py`; that unrelated user change was not overwritten.
