# MeaningSync Roadmap

## Implemented

- Deterministic English/INR Homeowner/Electrician Demo using the same six visible steps as Live
- Conversation-first Preferences, Participation, Conversation, Check understanding, Confirm, and Receipt UI
- Generic Live Customer/Service provider roles; either role may create and invite the opposite role
- Shared-device and separate-device participation with role-bound credentials, single-use QR/link joining, presence, and revision-aware polling
- Independent English/Hindi language selection and validation, and INR/USD/EUR session metadata without evidence conversion
- Role-scoped chat, per-role readiness, explicit creator-only comparison, and no analysis per message
- Type/Speak per Live turn with participant consent, transcription-only WebRTC, transcript review/correction, typed fallback, and no raw-audio storage
- Backend-only Responses API Structured Outputs, atomic agreement items, evidence hydration, partial warnings, and controlled errors
- Matches / Needs a decision / Not discussed agreement map with evidence on every non-missing term
- Hidden private choices, compatible deterministic resolution, disagreement non-repetition, and optional missing topics without mandatory teach-back
- Immutable meaningful versions, Conversation re-entry, separate confirmations, and invalidation after changes
- Durable state-v5 SQL sessions/receipts, migration from v1/v2/v3/v4, restart recovery, persistent translation/consent/idempotency, optimistic revisions, and TTL expiry
- Receipts preserving roles, languages, currency/evidence provenance, timestamps, history, unresolved/missing items, disclaimer, and integrity hash

## Partially Implemented

- Expiry is enforced, but automatic cleanup, backup, deletion tooling, and privacy-preserving observability are not implemented
- Role authorization does not verify identity and shared-device handoff is only a presentation boundary
- Automated and manual responsive checks exist; moderated usability research is still needed

## Planned

1. Run moderated first-click and end-to-end usability studies.
2. Run explicitly authorized model evaluations and human review of decision wording.
3. Add retention cleanup, backup/deletion operations, and privacy-preserving observability.


Identity/signature services, custom PDFs, payments, and legal-contract generation remain separate product decisions. MeaningSync does not imply those capabilities.
