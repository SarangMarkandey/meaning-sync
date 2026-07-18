# MeaningSync Product Specification

## Product Promise

MeaningSync helps two people determine whether their stated understanding of a verbal service agreement matches: “Make sure both sides mean the same thing.” It is not a legal-contract generator, signature service, identity platform, or generic mediator, and it does not provide legal advice.

## Implemented Journey

Demo and Live show exactly six steps:

`Preferences → Participation → Conversation → Check understanding → Confirm → Receipt`

| Step | User action | Product rule |
| --- | --- | --- |
| Preferences | Choose each person’s language and session currency. | English is implemented. Live supports INR/USD/EUR; Demo is fixed to English/INR. Currency metadata never converts original evidence. |
| Participation | Choose Customer or Service provider and shared or separate devices. | Either role may create. A separate-device invite always belongs to the opposite role. |
| Conversation | Exchange role-scoped text messages and independently mark ready. | Both people must speak and be ready before the creator can compare. New text clears readiness and confirmations. Messages never trigger analysis. |
| Check understanding | Review Matches, Needs a decision, and Not discussed. | Non-missing items show original evidence. Only conflicts/one-sided items need private choices. The first choice stays hidden. Missing topics are optional. |
| Confirm | Each person confirms the same current version or requests a change. | A change returns to Conversation for the selected item and invalidates current confirmations. |
| Receipt | Review the immutable outcome. | Matching, unresolved, one-sided, and missing items all remain visible. The receipt is not a legal contract. |

`analyzing` is a transient loading state at the start of Check understanding. Clarification is an interaction within that step, not separate progress. The frontend has one central mapping from server lifecycle stages to the six visible steps.

## Meaning and Evidence Rules

Only explicit participant statements and selections can change agreement meaning. An aligned non-missing term requires evidence from both people. Conflicts and one-sided terms use neutral options derived from recorded positions, plus **Something else** and **I’m not sure**. Compatible choices may create an immutable child agreement version. Different choices do not create agreement, do not immediately repeat the same question, and may be discussed again or left unresolved. There is no mandatory teach-back or minimum question count.

Every successful analysis is retained as an immutable internal snapshot. A user-facing Agreement Map number advances only when a deterministic semantic fingerprint changes. IDs, timestamps, provider metadata, and wording-only differences do not create a new visible version.

## Participation and Privacy

Shared-device mode uses visible role switching and handoff; it is not authentication. Separate-device mode uses expiring, role-bound bearer credentials, a single-use invitation, local QR rendering, URL-fragment removal, and revision-aware polling. The invited participant joins with one action, and both devices leave the waiting screen automatically after connection. Neither path verifies identity or proves consent or comprehension.

## Receipt Content

Two separate current-version confirmations are required. The receipt records roles, languages, session currency, original evidence and its stated currencies, session and confirmation times, immutable agreement history, unresolved/missing terms, and a canonical SHA-256 integrity hash. The hash is not a signature.

## Status

**Implemented:** deterministic English/INR Demo; conversation-first shared/separate Live; creator-selectable generic roles; INR/USD/EUR metadata; readiness-gated explicit analysis; private choice comparison; immutable versions; separate confirmation; durable sessions/receipts; restart recovery; expiry; optimistic concurrency; and persistent idempotency.

**Planned:** moderated usability validation, Hindi and translation, audio with explicit recording consent, automated cleanup/backups/deletion, and privacy-preserving observability. MeaningSync records stated meaning; it does not provide legal advice or create an enforceable agreement.
