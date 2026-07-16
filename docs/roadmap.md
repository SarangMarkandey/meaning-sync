# MeaningSync Roadmap

## Implemented

- Deterministic English homeowner/electrician demo with consent, hidden clarification answers, confirmations, and clarity receipt
- Shared `aligned`, `conflicting`, `stated_by_one`, and `not_discussed` domain contract
- English text-based Live conversation entry with add/edit/remove/sample input
- Backend-only OpenAI Responses API integration using Pydantic Structured Outputs
- Prompt version `agreement-analysis-v4`, trusted clarification context, nested clarification ownership, atomic topic/facet keys, `store=False`, evidence hydration, partial analysis warnings, and controlled failures
- Twelve-case English evaluation corpus; mocked tests spend no credits
- Server-owned English Live lifecycle with exact separately answered clarification, bounded retries, and immutable parent-linked agreement versions
- Guided five-stage Live UI—Conversation, Clarify, Review, Confirm, Receipt—with Setup before progress and a dedicated analyzing transition
- Server-derived next-action guidance, deterministic required-issue priority, exact-target clarification fingerprints/deduplication, and progressive disclosure
- Required-versus-optional treatment, explicit unresolved continuation, and batched optional-detail statements
- Meaningful user-facing Agreement Map numbers backed by semantic fingerprints while every internal analysis event remains immutable
- Same-device Homeowner/Electrician handoff with backend teach-back comparison and focused follow-up or exact-item reopening
- Separate participant/version/teach-back-bound confirmations, stale-version protection, request-ID idempotency, and invalidation after changes
- In-memory Live clarity receipt with aligned and unresolved categories, evidence, clarification history, separate timestamps, disclaimer, and payload-change hash

## Partially Implemented

- Independent `en`/`hi` language settings and translation interface; only English flows are enabled
- Session recovery and receipts remain process-local; refresh works only while the same FastAPI process retains the session
- Same-device privacy cues without authentication, identity verification, or a secure participant boundary
- First-click and responsive usability criteria are automated/manually checked, but moderated usability research has not yet been run

## Planned Milestones

1. Run moderated first-click and end-to-end usability studies without changing the server-owned safety rules.
2. Evaluate agreement analysis and teach-back semantics with explicitly authorized opt-in model runs and human review.
3. Add durable session/receipt persistence, restart recovery, retention/deletion controls, and privacy-preserving observability.
4. Add authenticated separate-device QR joining and realtime session updates.
5. Add Hindi UI, Hindi analysis, optional translation, and bilingual receipts while preserving original evidence.
6. Add audio capture/playback with explicit recording consent and privacy controls.
7. Expand safety review; identity/signature services and custom PDF output remain separate product decisions, not implied capabilities.

Planned features are not represented as working. MeaningSync does not provide legal advice or create a legally enforceable document.
