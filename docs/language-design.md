# Language Design

## Principles

- Meaning comparison is the product; translation is optional support.
- Homeowner and electrician languages are independent, never a pair enum.
- Original text, language, speaker, message ID, order, and timestamp remain immutable evidence.
- Translated display text must never replace or silently alter original evidence.

## Current Behavior

| Participants | Translation needed | Status |
| --- | --- | --- |
| English ↔ English | No | Demo and live text preview implemented |
| Hindi ↔ Hindi | No for basic display | Data model only; planned |
| English ↔ Hindi | Yes for one or both displays | Boundary only; planned |

Both `/demo/setup` and `/live/setup` provide separate, accessible selectors. English defaults for both participants. Hindi is labelled “Coming soon,” disabled, and cannot reach analysis. Live API validation independently rejects non-English participants or messages; it never translates silently.

Evidence expansion always labels the speaker and shows the exact original English statement with message order and timestamp. Meaning states are also expressed in text, not colour alone.

## Status

Implemented: English inputs and immutable evidence. Partially implemented: ISO `en`/`hi` fields and an optional translation-service interface. Planned: Hindi UI/content, language detection, provider-backed translation, cross-language analysis evaluation, and bilingual clarity receipts. MeaningSync does not provide legal advice.
