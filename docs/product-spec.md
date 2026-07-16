# MeaningSync Product Specification

## Product Promise

MeaningSync helps two people determine whether their stated understanding of a verbal service agreement matches: “Make sure both sides mean the same thing.” It is not a legal-contract generator, signature service, identity platform, or generic mediator, and it does not provide legal advice.

## Implemented Experiences

The deterministic path is:

`Homepage → Demo setup → Consent → Prepared evidence → Agreement map → Private clarification → Teach-back confirmations → Clarity receipt`

The English live-text preview is:

`Homepage → Live setup → Speaker-attributed text → Analyze → Agreement map → Evidence → Neutral clarification`

Users can add, edit, remove, or load sample statements. Analysis requires meaningful input from both people. The agreement map groups `aligned` as **Confirmed**, `conflicting` and `stated_by_one` as **Needs clarification**, and `not_discussed` as **Not discussed**. Only explicit evidence from both people can produce alignment.

The required sample shows alignment on price amount and starting today, plus a materials-inclusion conflict about replacement parts. Evidence always links to original messages. If only the clarification is unusable, Live Mode preserves the agreement map and shows a partial-analysis warning; invalid core analysis shows safe retry guidance without fixture fallback.

## Status

**Implemented:** deterministic English demo and receipt, English live-text entry and OpenAI Structured Outputs, original evidence, semantic post-validation, and safe errors.

**Partially implemented:** independent English/Hindi language fields and a translation boundary; Hindi remains disabled.

**Planned:** audio with explicit consent, Hindi and translation, QR/device joining, realtime updates, persistence, separate live confirmations, and a live clarity receipt. The current live result is an agreement map, not a receipt or legal document.
