# Language Design

## Principles

- Meaning comparison is the product; translation is optional support.
- Homeowner and electrician languages are independent, never a pair enum.
- Original text, language, speaker, message ID, order, and timestamp remain immutable evidence.
- Translated display text must never replace or silently alter original evidence.

## Current Behavior

| Participants | Translation needed | Status |
| --- | --- | --- |
| English ↔ English | No | Demo and complete same-device Live text flow implemented |
| Hindi ↔ Hindi | No for basic display | Data model only; planned |
| English ↔ Hindi | Yes for one or both displays | Boundary only; planned |

Both `/demo/setup` and `/live/setup` provide separate, accessible selectors. English defaults for both participants. Hindi is labelled “Coming soon,” disabled, and cannot reach analysis. Live API validation independently rejects non-English participants or messages; it never translates silently.

The guided Live progress labels—Conversation, Clarify, Review, Confirm, and Receipt—and all server-supplied guidance are currently English-only. Setup precedes the progress indicator, and the transient analyzing message stays within the Conversation transition. Future localization must translate labels and guidance without changing item keys, version fingerprints, evidence, or lifecycle authority.

Evidence expansion always labels the speaker and shows the exact original English statement with message order and timestamp. Meaning states are also expressed in text, not colour alone.

Clarification answers are stored as immutable messages in each participant’s declared language. Live teach-back currently accepts English and records `original_language`; each confirmation and receipt participant record also preserves language. No component silently translates evidence, clarification, teach-back, or receipt text.

## Status

Implemented: English inputs, the five-stage English guidance vocabulary, immutable evidence/clarification messages, English teach-back, and receipt language provenance. Partially implemented: ISO `en`/`hi` fields and an optional translation-service interface. Planned: Hindi UI/content, localized guidance, language detection, provider-backed translation, cross-language analysis evaluation, and bilingual clarity receipts. MeaningSync does not provide legal advice.
