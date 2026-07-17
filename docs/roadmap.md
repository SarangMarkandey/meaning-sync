# MeaningSync Roadmap

## Implemented

- Deterministic English homeowner/electrician demo with consent, hidden clarification answers, confirmations, and clarity receipt
- Shared `aligned`, `conflicting`, `stated_by_one`, and `not_discussed` domain contract
- English text-based Live conversation entry with add/edit/remove/sample input
- Backend-only OpenAI Responses API integration using Pydantic Structured Outputs
- Prompt version `agreement-analysis-v4`, trusted clarification context, nested clarification ownership, atomic topic/facet keys, `store=False`, evidence hydration, partial analysis warnings, and controlled failures
- Twelve-case English evaluation corpus; mocked tests spend no credits
- Server-owned English Live lifecycle with exact separately answered clarification, bounded retries, and immutable parent-linked agreement versions
- Guided five-stage Live UI—Conversation, Clarify, Check understanding, Confirm, Receipt—with Setup before progress and a dedicated analyzing transition
- Server-derived next-action guidance, deterministic required-issue priority, exact-target clarification fingerprints/deduplication, and progressive disclosure
- Required-versus-optional treatment, explicit unresolved continuation, and batched optional-detail statements
- Meaningful user-facing Agreement Map numbers backed by semantic fingerprints while every internal analysis event remains immutable
- Deterministic choice construction with stable semantic options, at most one additional check after completed clarification, a three-check cap without clarification, semantic deduplication, and safe stage skipping
- Same-device Homeowner/Electrician handoff with hidden first selection, `Something else` and uncertainty handling, versioned changes, and exact-item reopening
- Separate participant/version/understanding-review-bound confirmations, stale-version protection, request-ID idempotency, and invalidation after changes
- Durable SQL-backed Live sessions and clarity receipts with validated versioned JSON, restart recovery, persistent idempotency, optimistic revisions, TTL expiry, and Alembic migrations

## Partially Implemented

- Independent `en`/`hi` language settings and translation interface; only English flows are enabled
- TTL retention is enforced, but automatic expired-row cleanup, backup, deletion tooling, and privacy-preserving observability are not yet implemented
- Same-device privacy cues without authentication, identity verification, or a secure participant boundary
- First-click and responsive usability criteria are automated/manually checked, but moderated usability research has not yet been run

## Planned Milestones

1. Run moderated first-click and end-to-end usability studies without changing the server-owned safety rules.
2. Evaluate agreement analysis with explicitly authorized opt-in model runs, and evaluate understanding-choice clarity with moderated human review.
3. Add P1B role-bound participant tokens, single-use invite exchange, QR joining, participant-specific authorization, and lightweight synchronization.
4. Add automatic retention cleanup, backup/deletion operations, and privacy-preserving observability.
5. Add Hindi UI, Hindi analysis, optional translation, and bilingual receipts while preserving original evidence.
6. Add audio capture/playback with explicit recording consent and privacy controls.
7. Expand safety review; identity/signature services and custom PDF output remain separate product decisions, not implied capabilities.

Planned features are not represented as working. MeaningSync records independent selections; it does not prove comprehension, identity, consent, or legal enforceability, provide legal advice, or create a legally enforceable document.
