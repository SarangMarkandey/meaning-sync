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

## UI Repair — Demo Setup Layout

**Date:** 2026-07-15

- Confirmed the project uses `globals.css` (imported by the root layout) plus Tailwind, with no CSS modules or missing stylesheet import. Setup JSX class names match the global selectors.
- Repaired the partially applied setup presentation with a centered 1040px page container, 940px form, responsive two-column card grid, equal card padding, explicit label/select layout, and a visible select affordance.
- Separated the selected-conversation panel from availability messaging, aligned equal-height actions, and removed the duplicate top-right “Demo setup” pill.
- Preserved visible keyboard focus, semantic labels, English defaults, disabled Hindi options, URL-based language transfer, and all existing demo behavior.

Verification:

- `npm run lint`: passed.
- `npm run type-check`: passed.
- `npm test`: 11 passed.
- `npm run build`: passed.
- Browser inspection passed at 1440×900, 1024×768, and 390×844 with no clipping or horizontal overflow.
- Computed styles confirmed the setup container, grid, cards, selects, and actions receive their intended rules. Chrome reported no CSS, hydration, or React errors.

## Milestone 3 — OpenAI-Powered English Agreement Analysis

**Date:** 2026-07-16

- Added `/live/setup` and `/live` for independent English language setup and a polished text-only workspace with add, edit, remove, sample, minimum-input, loading, safe error, retry, result, clarification, and evidence states.
- Added `POST /api/v1/agreements/analyze`, the shared four-state agreement contract, `AgreementAnalyzer` protocol, stable deterministic implementation, and backend-only `OpenAIAgreementAnalyzer`.
- Integrated OpenAI Responses API Pydantic Structured Outputs with model `gpt-5.6`, prompt `agreement-analysis-v1`, `store=False`, a 30-second timeout, and no live-to-fixture fallback.
- Added application-owned evidence hydration and validation for participant ownership, both-party alignment/conflicts, one-sided statements, topic uniqueness, and clarification targeting.
- Added 12 English semantic evaluation fixtures plus a paid integration harness gated by `RUN_OPENAI_INTEGRATION=1`.
- Updated all product, architecture, API, language, roadmap, setup, analysis, integration, and evaluation documentation.

Verification:

- `ruff format --check .` and `ruff check .`: passed.
- `pytest`: 27 passed, 12 opt-in integration cases skipped.
- `npm run lint` and `npm run type-check`: passed.
- `npm test`: 18 passed.
- `npm run build`: passed; routes include `/`, `/demo`, `/demo/setup`, `/live`, and `/live/setup`.
- FastAPI import/startup and `GET /health`: passed.
- Manual key-free Demo Mode produced aligned price/timing, conflicting materials, one-sided scope, and preserved not-discussed topics with correct evidence counts.
- Manual missing-key Live request returned safe `configuration_error` (HTTP 503) without fallback.
- Headless Chrome inspection passed at 1440×900 and 390×844 for live setup and workspace with no visible clipping or horizontal overflow.

No paid model evaluation ran during the initial milestone verification. Audio, audio consent, Hindi analysis, translation, QR/device joining, persistence, separate live confirmations, and the live clarity receipt remain planned.

### Paid Live-Flow Follow-up

**Date:** 2026-07-16

- Reused the locally configured, ignored `OPENAI_API_KEY` and sent one authorized paid request through FastAPI using model `gpt-5.6` and prompt `agreement-analysis-v1`.
- The endpoint returned HTTP 200. Timing was aligned, materials conflicted, missing topics remained not discussed, and hydrated evidence retained the correct participants, message IDs, order, and original language.
- The semantic check did not fully pass: price was also marked conflicting, both price and materials declared a `price` clarification target, and the resulting `clarify-price` question referenced the materials term. The required example expects the amount/coverage distinction and one materials clarification.
- No additional paid requests were made. The analyzer prompt and post-validation require correction and a focused regression test before another live verification.

## Semantic and Live UI Repair

**Date:** 2026-07-16

- Added canonical atomic agreement items (`price.amount`, `materials.inclusion`, `timing.start`, and related core keys) so amount, coverage, start, and completion meanings cannot be conflated.
- Updated prompt `agreement-analysis-v2` to decompose compound claims, reject silence-based agreement and duplicate broad/specific items, and target one smallest neutral clarification.
- Hardened post-validation so a clarification must match one unique conflict/one-sided term by item key, topic, facet, and the exact evidence set. Unsafe or duplicated model output now returns the controlled invalid-output error.
- Added a sanitized offline fixture for the observed price/materials failure plus regression coverage for aligned price, conflicting materials, missing topics, duplicate items, unrelated targets, and evidence mismatch.
- Confirmed the raw live-page regression does not reproduce in a clean production build: the root global stylesheet is loaded and its live selectors apply. Hardened the page with an 1100px content cap, explicit form IDs/labels, textarea/summary focus rings, and 40–44px text-action targets.
- Added focused DOM/CSS contract tests for the centered workspace, desktop grid, card presentation, mobile stack, and accessible fields.

Verification:

- `ruff format --check .` and `ruff check .`: passed.
- `pytest -q`: 31 passed, 12 opt-in paid integration cases skipped.
- `npm run lint` and `npm run type-check`: passed.
- `npm test -- --run`: 20 passed.
- `npm run build`: passed with `/`, `/demo`, `/demo/setup`, `/live`, and `/live/setup` generated.
- Production Chrome inspected the homepage, both setup routes, empty/one-party/two-party/sample/edit/delete/loading/configuration-error/retry/success states, conflict/one-sided/not-discussed results, clarification, and expanded evidence.
- Responsive checks passed at 1440×900, 1024×768, 768×1024, 390×844, and 360×800. Computed styles showed the centered 1100px cap, desktop two-column grid, mobile single-column stack, associated field labels, usable action heights, and no horizontal overflow.
- Browser console inspection found no CSS, hydration, or React errors. The only resource errors were the intentionally mocked HTTP 503 and 504 failure-state responses.

No OpenAI request—paid or otherwise—was made during this repair.

## Clarification Ownership Reliability Repair

**Date:** 2026-07-16

- Diagnosed the HTTP 502 as a detached-reference failure: the model separately produced a valid `materials.inclusion` conflict and a clarification marker pointing at `price.amount`. Application term IDs were generated later and were not the cause.
- Replaced model-generated clarification targets and evidence lists with one optional question nested on its exact agreement item. The backend now derives the public target, topic, facet, term ID, and unchanged evidence from that owner.
- Added deterministic legacy resolution by exact item key, exact topic/facet, unique unresolved evidence overlap, or a sole unresolved item. Broad or ambiguous matches are never guessed.
- Added `complete`/`partial` analysis status and `clarification_unavailable`. A valid core map with an invalid clarification returns HTTP 200 and remains visible; invalid core terms or evidence still return a controlled HTTP 502.
- Updated the live UI with a distinct partial-analysis warning while preserving all map sections and evidence.
- Added offline backend and frontend regressions for nested ownership, invalid states, multiple candidates, duplicate keys, ambiguity, evidence integrity, partial success, and map rendering.

Verification:

- `ruff format --check .` and `ruff check .`: passed (25 Python files).
- `pytest -q -ra`: 38 passed; 12 paid integration cases skipped by default.
- `npm run lint` and `npm run type-check`: passed.
- `npm test -- --run`: 21 passed across 6 files.
- `npm run build`: passed; `/`, `/demo`, `/demo/setup`, `/live`, and `/live/setup` generated.
- `git diff --check`: passed.

No OpenAI request—paid or otherwise—ran during this repair. The implementation is ready for exactly one separately authorized paid verification.
