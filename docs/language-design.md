# Language Design

## Principles

- Agreement meaning is the product; translation is optional support.
- Participant languages are independent, never a fixed pair enum.
- Original text and original language are immutable evidence.
- Translations are additional display values keyed by target language.
- Analysis must not silently replace original evidence with translated text.

## Language Behavior

| Participants | Translation requirement | Current status |
| --- | --- | --- |
| English ↔ English | None; the translation service must not be called | Implemented demo |
| Hindi ↔ Hindi | None for normal participant display | Model only; planned flow |
| English ↔ Hindi | May be needed independently for each display | Boundary only; planned provider and flow |

The current language codes are strict ISO 639-1 `en` and `hi`. Adding a language extends `LanguageCode`; it does not require defining all language pairs. Both demo participants default to `en`.

Language choice occurs after **Try Demo** on `/demo/setup`, never on the homepage. Homeowner and electrician controls are independent. The selection summary is textual as well as visual, URL parameters preserve the values on refresh, and only `en`/`en` can currently start. Hindi remains visible as a disabled coming-soon choice. The future Live setup will use the same independent model.

## Evidence and Accessibility

Messages retain message/session IDs, participant, original text, original language, timestamp, and optional translations. Evidence inspection always labels and shows the original participant statement. Future translated display should provide a clear control to return to the original, announce the active language to assistive technology, preserve reading order, and avoid using color alone to distinguish agreement status.

## Implementation Truth

The English-only demo, route validation, and same-language translation bypass are implemented and tested. Independent Hindi values are valid in backend models, but the setup UI labels Hindi as planned and blocks unsupported flows. There is no production translation service, Hindi agreement fixture, language detection, or bilingual clarity receipt yet.
