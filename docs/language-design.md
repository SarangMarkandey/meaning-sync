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

The guided Live progress labels—Conversation, Clarify, Check understanding, Confirm, and Receipt—and all server-supplied guidance are currently English-only. Setup precedes the progress indicator, and the transient analyzing message stays within the Conversation transition. Future localization must translate labels, question prompts, and option labels without changing backend-owned option IDs, semantic values, item keys, version fingerprints, evidence, or lifecycle authority.

Evidence expansion always labels the speaker and shows the exact original English statement with message order and timestamp. Meaning states are also expressed in text, not colour alone.

Clarification and understanding selections bind a stable semantic value independently of their displayed English label. `Something else` text is preserved in the acting participant’s declared language and enters the existing immutable message/version flow only when required by the outcome. Each confirmation and receipt participant record also preserves language. No component silently translates evidence, selection text, clarification, or receipt content.

## Status

Implemented: English inputs, the five-stage English guidance vocabulary, immutable evidence/clarification messages, deterministic English choice labels with stable semantic values, and receipt language provenance. Partially implemented: ISO `en`/`hi` fields and an optional translation-service interface. Planned: Hindi UI/content, localized guidance and options, language detection, provider-backed translation, cross-language analysis evaluation, and bilingual clarity receipts. MeaningSync records selections; it does not prove comprehension or provide legal advice.
