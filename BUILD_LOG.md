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

## Milestone 4 — Clarification, Confirmation, and Clarity Receipt

**Date:** 2026-07-16

- Replaced the stateless Live result with a server-owned in-memory lifecycle from conversation draft through analysis, exact clarification, independent teach-backs, separate confirmations, and receipt issuance.
- Added immutable, monotonically numbered agreement snapshots. Clarification answers and additional statements append immutable speaker-attributed messages; successful re-analysis creates a child version instead of overwriting the prior map.
- Added optimistic agreement-version checks, request-ID idempotency, actor-bound same-device handoffs, and automatic invalidation of confirmations when a newer version is created.
- Kept the first clarification answer hidden until the second participant submits. The resulting answers are re-analyzed through the configured Live analyzer with no deterministic fallback; repeated attempts are bounded by `MEANINGSYNC_CLARIFICATION_ATTEMPT_LIMIT`.
- Added backend-only Structured Outputs teach-back comparison with `matches`, `partially_matches`, `contradicts`, and `insufficient` states. Partial responses receive a focused follow-up; contradictions reopen the exact agreement item.
- Added separate, version- and teach-back-bound confirmation records plus an immutable receipt containing aligned, conflicting, one-sided, not-applicable, and not-discussed categories, clarification history, both confirmation timestamps, the required disclaimer, and a deterministic payload-change hash.
- Added Live session, agreement-version, clarification, statement, not-applicable, review, teach-back, confirmation-status, and receipt JSON endpoints plus controlled lifecycle, stale-version, participant, and readiness errors.
- Added the same-device Live workflow and receipt routes with progress, version comparison, handoff privacy cues, unresolved-item acknowledgment, print/save through browser printing, and truthful missing-session recovery.

Verification status:

- Pre-implementation baseline passed: backend formatting/lint, 38 backend tests with 12 paid cases skipped, FastAPI import, frontend lint/type-check, 21 frontend tests, and production build.
- `ruff format --check .` and `ruff check .`: passed across 37 Python files.
- `pytest -ra`: 61 passed; 12 real-OpenAI evaluation cases skipped by default because they consume API credits.
- FastAPI import and OpenAPI generation: passed with 13 Live session paths.
- `npm run lint`, `npm run type-check`, and `npm test -- --run`: passed; 35 frontend tests passed across 8 files.
- `npm run build`: passed with `/live`, `/live/[sessionId]`, and `/live/[sessionId]/receipt` included in the production route output.
- Real-browser verification covered 16 required Live states at 1440×900, 1024×768, 768×1024, 390×844, and 360×800 (80 captures). Every capture had viewport-width content with no horizontal overflow or clipped controls. Desktop, tablet, and mobile spot checks confirmed readable handoffs, hidden-first-answer treatment, version comparison, confirmations, and both receipt statuses.
- Browser interaction exercised create, analyze, exact clarification, hidden first response, immutable v2, separate teach-backs, separate confirmations, receipt issuance, contradiction reopening, stale-version recovery, and missing-session recovery. No CSS, hydration, React, or runtime exceptions appeared; the only browser network errors were the intentionally exercised `409` stale-version and `404` missing-session responses.
- `git diff --check`: passed after the final documentation update.
- No paid OpenAI request ran during this milestone implementation. Normal and UI tests use deterministic or mocked analyzers/evaluators.

Current limits: sessions and receipts disappear on backend restart; same-device handoff is not authentication or strong privacy; English text only; no audio, QR joining, separate devices, database, identity verification, electronic signature, custom PDF, or legal-contract status.

## Guided Live Workflow and Meaningful Versions

**Date:** 2026-07-17

- Simplified the user-visible Live journey to five stable stages: Conversation, Clarify, Review, Confirm, and Receipt. Setup remains before progress; analyzing is a dedicated transient state during the move out of Conversation.
- Added server-derived guidance for the current user stage, one primary action, optional secondary action, acting participant, exact clarification target, and required/optional item sets. The browser no longer needs to infer the next step from stale clarification history.
- Defined deterministic required-issue priority as scope, amount and price coverage, materials, timing, payment, then other critical responsibility, with stable agreement-item ordering for ties.
- Added exact-target clarification fingerprints and deduplication so equivalent active questions are reused while distinct atomic meanings remain separate.
- Separated immutable internal analysis events from meaningful user-facing Agreement Map versions. The semantic fingerprint includes normalized state, participant positions and statuses, evidence-backed missing-to-stated transitions, and mutually acknowledged not-applicable treatment while excluding neutral-summary wording, IDs, timestamps, and provider metadata.
- Kept required conflicts and critical one-sided meanings blocking until resolved or explicitly carried unresolved. Grouped ordinary not-discussed topics under progressively disclosed optional details, with one deliberate multi-message batch available instead of a forced request per topic.
- Preserved same-device handoffs for hidden clarification responses, separate teach-backs, and separate confirmations. The UI continues to state that this is not authentication or strong privacy.
- Added first-click criteria: one obvious primary action, safe Back behavior, evidence on demand, no navigation-as-consent, duplicate-submit prevention during loading, and truthful stale/missing-session recovery.
- Updated the product, architecture, API, analysis, clarification, receipt, language, privacy, OpenAI, evaluation, roadmap, and setup documentation without removing the historical Milestone 4 record.

Final verification results:

- `ruff format --check .` and `ruff check .`: passed across 39 Python files.
- `pytest -ra`: 70 passed; 12 real-OpenAI evaluation cases skipped because they are opt-in and consume API credits.
- FastAPI import and OpenAPI generation: passed with 25 paths.
- `npm run lint`, `npm run type-check`, and `npm test -- --run`: passed; 40 frontend tests passed across 8 files.
- `npm run build`: passed with 8 application routes, including the dynamic Live session and receipt routes.
- Production Chrome exercised 18 states from language setup through receipt, plus missing-session and stale-version recovery, at 1440×900, 1024×768, 768×1024, 390×844, and 360×800. The audit produced 90 viewport checks and 126 screenshots.
- The exact Agreement Map v5 fixture rendered 4 matching meanings, 1 required scope answer, and 5 optional not-discussed details. Every tested screen exposed one clear primary action or an intentional analyzing state.
- Browser checks found no horizontal overflow, clipped interactive controls, unlabeled form controls, raw internal terminology, CSS/hydration/React exceptions, or unexpected console errors. The only resource errors were the intentionally exercised `404` missing-session and `409` stale-version responses.
- Visual inspection covered setup, conversation, analyzing, summary, clarification, resolved outcome, optional details, final review, both private teach-backs, both confirmations, receipt-ready, receipt, expanded integrity details, missing session, and stale version on desktop and mobile.
- Browser verification exposed and fixed a stale local Review view after starting teach-back; validated provider questions without choices now retain application-owned safe options.
- `git diff --check`: passed. No paid OpenAI request ran during implementation or verification; the browser harness blocked OpenAI client creation and used deterministic local fixtures.

## Choice-Based Clarification and Understanding Checks

**Date:** 2026-07-17

- Replaced the user-facing Teach-back/Review step with **Check understanding** while preserving the server-owned lifecycle, immutable agreement versions, evidence provenance, separate confirmations, and clarity receipt.
- Added shared `UnderstandingQuestion`, `UnderstandingOption`, and private participant-selection records for clarification and understanding-check questions. Stable option IDs and semantic values are bound to the exact session, participant, agreement item, immutable version, and supporting evidence.
- Constructed neutral choices deterministically from recorded positions or shared meaning. Every question includes `Something else` and `I'm not sure`; short text is required only for `Something else`, and uncertainty never becomes alignment.
- Limited Check understanding to at most one additional high-impact question after a completed two-party clarification; sessions without clarification retain the one/two-question simple-agreement policy and three-question broad-agreement cap. Server-owned independent-evidence tracking prevents wording-level duplicates and suppresses items already independently answered during clarification.
- Preserved same-device privacy handoffs: the first participant's selection, semantic value, text, and selection ID are omitted from the public response until every addressed participant answers.
- Added deterministic outcomes for recorded alignment, a shared alternative that enters the immutable version-change flow, different meanings that reopen only one item, uncertainty, and deliberate unresolved continuation. New meaningful versions invalidate stale confirmations.
- Bound separate confirmations to the participant's current understanding review and changed the `clarity-receipt-v2` completion data from teach-back status to understanding status. Receipts continue to preserve unresolved and not-discussed meaning and the required legal disclaimer.
- Updated Live UI copy and interaction to one accessible choice question at a time, visible progress, one **Submit my choice** action, conditional free text, neutral handoff/outcome screens, and the five visible stages Conversation, Clarify, Check understanding, Confirm, and Receipt.
- Updated setup, product, architecture, API, analysis, clarification, receipt, language, privacy, OpenAI, evaluation, and roadmap documentation. MeaningSync records independent selections and makes differences visible; it does not prove comprehension, identity, consent, or legal enforceability.
- Documented how Codex supported architecture inspection, implementation, tests, and usability iteration while the builder retained the core product decisions; kept GPT-5.6 as the final hackathon agreement-analysis model.
- Finalized the post-clarification policy: a current meaning with completed two-party clarification receives at most one additional Check understanding question, or proceeds directly to separate confirmation when none remains. Sessions without clarification retain the one/two/three-question policy.
- Remaining limitations are same-device participation, process-local storage, no authentication or role-bound participant token, no QR joining or realtime synchronization, and English text only.

Final verification results:

- `ruff format --check .`: passed; 42 files formatted. `ruff check .`: passed.
- `pytest`: 87 passed; 12 paid OpenAI evaluation cases skipped by default.
- FastAPI import/OpenAPI generation: passed with 24 paths.
- `npm run lint` and `npm run type-check`: passed.
- `npm test -- --run`: 46 passed across 9 files.
- `npm run build`: passed with Next.js 16.2.10 and all 8 application routes generated.
- No browser automation or paid OpenAI request ran during this completion pass.

## P1A — Durable Live Sessions

**Date:** 2026-07-17

- Replaced the Live service's process-global session dictionary with one repository abstraction and explicit in-memory test and SQL production/local implementations.
- Persisted the complete Live workflow as Pydantic-validated `state-v1` JSON, including messages, immutable versions, internal question semantics, private selections, reviews, confirmations, evidence, receipts, optional-detail status, and request-ID digests.
- Added optimistic repository revisions so each mutation commits atomically against the loaded row. Concurrent updates fail with a controlled conflict; failed final selections leave no partial state.
- Split analysis into short transactions around the external await: persist `analyzing`, release the database, then commit only against the expected revision or restore a retryable stage on failure.
- Added SQLAlchemy 2.x storage, PostgreSQL support, ignored local SQLite, Alembic migrations, a uv lockfile, bounded session TTL, controlled HTTP 410 expiry, invalid-state protection, and startup/shutdown resource management.
- Preserved the public Live JSON contract, hidden first selections, persistent idempotency, immutable parent-linked versions, confirmation invalidation, receipt contents/hash, deterministic Demo Mode, GPT-5.6 default, and `store=False`.
- Kept the P1A interface same-device. Persistence is not authentication or participant privacy; role-bound tokens, invite exchange, QR joining, participant authorization, and synchronization remain P1B.

Final verification results:

- `ruff format --check .`: passed across 49 Python files; `ruff check .`: passed after correcting two local style findings.
- `pytest`: 97 passed and 12 opt-in paid OpenAI evaluations skipped; the 109-test collection includes 10 new persistence tests.
- FastAPI OpenAPI generation passed with 24 paths.
- A fresh SQLite database upgraded to Alembic revision `20260717_01`; a separate two-repository/two-service restart smoke test recovered the created session.
- `npm run lint`, `npm run type-check`, `npm test -- --run`, and `npm run build`: passed; 46 frontend tests passed across 9 files and Next.js 16.2.10 generated all 8 routes.
- No browser automation, Docker requirement, paid test, or OpenAI request ran.
