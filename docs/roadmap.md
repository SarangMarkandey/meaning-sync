# MeaningSync Roadmap

## Implemented

- Deterministic English/INR Homeowner/Electrician Demo using the same six visible steps as Live
- Conversation-first Preferences, Participation, Conversation, Check understanding, Confirm, and Receipt UI
- Generic Live Customer/Service provider roles; either role may create and invite the opposite role
- Shared-device and separate-device participation with role-bound credentials, single-use QR/link joining, presence, and revision-aware polling
- Independent language fields, English validation, and INR/USD/EUR session metadata without evidence conversion
- Role-scoped chat, per-role readiness, explicit creator-only comparison, and no analysis per message
- Backend-only Responses API Structured Outputs, atomic agreement items, evidence hydration, partial warnings, and controlled errors
- Matches / Needs a decision / Not discussed agreement map with evidence on every non-missing term
- Hidden private choices, compatible deterministic resolution, disagreement non-repetition, and optional missing topics without mandatory teach-back
- Immutable meaningful versions, Conversation re-entry, separate confirmations, and invalidation after changes
- Durable state-v3 SQL sessions/receipts, migrations from v1/v2, restart recovery, persistent idempotency, optimistic revisions, and TTL expiry
- Receipts preserving roles, languages, currency/evidence provenance, timestamps, history, unresolved/missing items, disclaimer, and integrity hash

## Partially Implemented

- Hindi fields/translation boundary exist, but only English is enabled
- Expiry is enforced, but automatic cleanup, backup, deletion tooling, and privacy-preserving observability are not implemented
- Role authorization does not verify identity and shared-device handoff is only a presentation boundary
- Automated and manual responsive checks exist; moderated usability research is still needed

## Planned

1. Run moderated first-click and end-to-end usability studies.
2. Run explicitly authorized model evaluations and human review of decision wording.
3. Add retention cleanup, backup/deletion operations, and privacy-preserving observability.
4. Add Hindi UI/analysis, optional translation, and bilingual receipts while preserving original evidence.
5. Add audio only with explicit recording consent and privacy controls.

Identity/signature services, custom PDFs, payments, and legal-contract generation remain separate product decisions. MeaningSync does not imply those capabilities.
