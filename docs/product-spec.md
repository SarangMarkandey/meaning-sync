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
| Conversation | Choose Type or Speak per turn, review every transcript, and independently mark ready. | Both people must contribute and be ready before comparison. New text or finalized transcript clears readiness and confirmations. Messages never trigger analysis. |
| Check understanding | Review Matches, Needs a decision, and Not discussed. | Non-missing items show original evidence. Only conflicts/one-sided items need private choices. The first choice stays hidden. Missing topics are optional. |
| Confirm | Each person confirms the same current version or requests a change. | A change returns to Conversation for the selected item and invalidates current confirmations. |
| Receipt | Review the immutable outcome. | Matching, unresolved, one-sided, and missing items all remain visible. The receipt is not a legal contract. |

`analyzing` is a transient loading state at the start of Check understanding. Clarification is an interaction within that step, not separate progress. The frontend has one central mapping from server lifecycle stages to the six visible steps.

## Meaning and Evidence Rules

Only explicit participant statements and selections can change agreement meaning. An aligned non-missing term requires evidence from both people. Conflicts and one-sided terms use neutral options derived from recorded positions, plus **Something else** and **I’m not sure**. Compatible choices may create an immutable child agreement version. Different choices do not create agreement, do not immediately repeat the same question, and may be discussed again or left unresolved. There is no mandatory teach-back or minimum question count.

Every successful analysis is retained as an immutable internal snapshot. A user-facing Agreement Map number advances only when a deterministic semantic fingerprint changes. IDs, timestamps, provider metadata, and wording-only differences do not create a new visible version.

## Participation and Privacy

Shared-device mode uses visible role switching and private handoff; it is not authentication. Audio is attributed to that explicit active role, never diarization. Separate-device mode uses expiring, role-bound bearer credentials and captures only the local bearer role; it is not an audio call. Before microphone access, each participant records session/role/notice-version consent. Every finalized transcript is reviewed, can be corrected without replacing machine text, and enters the same evidence ledger. MeaningSync stores no raw audio.

## Receipt Content

Two separate current-version confirmations are required. The receipt records roles, languages, session currency, original evidence and its stated currencies, session and confirmation times, immutable agreement history, unresolved/missing terms, and a canonical SHA-256 integrity hash. The hash is not a signature.

## Status

**Implemented:** deterministic English/INR Demo; conversation-first shared/separate Live; consent-gated reviewed WebRTC transcripts with typed fallback; creator-selectable generic roles; INR/USD/EUR metadata; readiness-gated analysis; private choices; immutable versions; separate confirmation; durable sessions/receipts; restart recovery; expiry; optimistic concurrency; and persistent idempotency.

**Planned:** moderated usability validation, Hindi and translation, automated cleanup/backups/deletion, and privacy-preserving observability. MeaningSync records stated meaning; it does not provide legal advice or create an enforceable agreement.
