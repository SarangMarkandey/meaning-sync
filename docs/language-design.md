# Language and Currency Design

## Principles

- Customer and Service provider languages are independent fields, never a pair enum.
- Original text, language, speaker, message ID, order, timestamp, amount, and stated currency remain immutable evidence.
- Translation or session-currency display must never replace, convert, or silently alter evidence.

## Current Behavior

English ↔ English is implemented for deterministic Demo and shared/separate Live. Hindi is visible as **Coming soon**, disabled in setup, and rejected by Live validation. Future translation may localize UI labels and display text, but backend-owned option IDs, semantic values, evidence, and version fingerprints must remain stable.

Live transcription receives the participant’s configured ISO language (`en`). It does not translate audio or replace the finalized machine transcript. Unsupported product languages remain rejected rather than silently relabeled.

Live supports INR, USD, and EUR as session metadata. Demo is the prepared English/INR scenario. The receipt records the session currency while evidence retains the currency actually stated; MeaningSync performs no conversion and does not infer unstated currency.

The English UI uses exactly Preferences, Participation, Conversation, Check understanding, Confirm, and Receipt. Generic Live labels are Customer and Service provider; Homeowner and Electrician remain specific to the prepared Demo.

## Status

Implemented: English typed and reviewed audio-transcript inputs, independent language fields, three Live session currencies, immutable evidence, deterministic English choice labels, and receipt provenance. Planned: Hindi UI/content, provider-backed translation, cross-language evaluation, and bilingual receipts.
