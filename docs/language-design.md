# Language and Currency Design

## Principles

- Customer and Service provider languages are independent fields, never a pair enum.
- Original text, language, speaker, message ID, order, timestamp, amount, and stated currency remain immutable evidence.
- Translation or session-currency display must never replace, convert, or silently alter evidence.

## Current Behavior

English/English, Hindi/Hindi, English/Hindi, and Hindi/English are implemented for shared- and separate-device Live. Demo offers deterministic English and prepared Hindi-Homeowner/English-Electrician presets. A typed English/Hindi dictionary localizes essential participant UI. Backend-owned option IDs, semantic values, evidence, and version fingerprints remain language-independent.

Live transcription receives the participant’s configured ISO language (`en` or `hi`). It does not translate audio or replace the finalized machine transcript. Unsupported product languages remain rejected rather than silently relabeled.

Live supports INR, USD, and EUR as session metadata. Both Demo presets use INR. The receipt records the session currency while evidence retains the currency actually stated; MeaningSync performs no conversion and does not infer unstated currency.

Mixed-language finalized messages are saved first, then translated outside the database transaction. Durable status is `pending`, `ready`, or `failed`; a stable fingerprint prevents duplicate translation. Failed translation never removes the original and can be retried. Same-language sessions create no translation work. Ready translations are derived context and display only—not original evidence.

Agreement terms and private options use stable semantic IDs with only the session-required localizations. Live GPT-5.6 Structured Output must provide faithful dynamic Hindi summaries and positions; FastAPI rejects a missing/mismatched required localization instead of substituting Demo wording. Different-language participants can select the same option ID. Hindi/Hindi receipts use Hindi-facing terms; mixed receipts show both languages with provenance and original evidence.

The English UI uses exactly Preferences, Participation, Conversation, Check understanding, Confirm, and Receipt. Generic Live labels are Customer and Service provider; Homeowner and Electrician remain specific to the prepared Demo.

## Status

Implemented: English/Hindi typed and reviewed audio-transcript inputs, independent language fields, three Live session currencies, immutable evidence, deterministic bilingual choice labels, provider-backed mixed-language translation, and bilingual receipt provenance. Broader cross-language evaluation remains future work; translation is not guaranteed perfect.
