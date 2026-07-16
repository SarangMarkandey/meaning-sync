# MeaningSync Product Specification

## Product Promise

MeaningSync helps two people determine whether their stated understanding of a verbal service agreement matches: “Make sure both sides mean the same thing.” It is not a legal-contract generator, signature service, identity platform, or generic mediator, and it does not provide legal advice.

## Implemented Experiences

The deterministic path is:

`Homepage → Demo setup → Consent → Prepared evidence → Agreement map → Private clarification → Teach-back confirmations → Clarity receipt`

The English same-device Live path uses five user stages:

`Conversation → Clarify → Review → Confirm → Receipt`

Setup precedes those stages. **Analyzing** is a dedicated transient state within the move from Conversation to Clarify or Review; it is never presented as a sixth destination or an actionable progress step.

| Stage | What users do | What MeaningSync shows first |
| --- | --- | --- |
| Conversation | Add speaker-attributed statements and deliberately request analysis. | Who has spoken, what is ready, and one Analyze action. |
| Clarify | Answer one exact neutral question or explicitly continue with that issue unresolved. | The highest-priority required issue, the two stated positions, and the acting participant. |
| Review | Read the current shared-understanding summary and complete separate same-device teach-backs. | Confirmed meaning and required acknowledgments; evidence and optional details remain expandable. |
| Confirm | Each participant confirms the same current meaningful version or requests a change. | Independent completion status and the participant currently holding the device. |
| Receipt | Read or print the immutable result. | Aligned meaning, a prominent unresolved warning when applicable, and separate confirmation times. |

Users can add, edit, remove, or load sample statements. Analysis requires meaningful input from both people. The agreement map groups `aligned` as **Confirmed**, `conflicting` and `stated_by_one` as **Needs clarification**, and `not_discussed` as **Not discussed**. Only explicit evidence from both people can produce alignment.

The required sample shows alignment on price amount and starting today, plus a materials-inclusion conflict about replacement parts. Evidence always links to original messages. If only the clarification is unusable, Live Mode preserves the agreement map and shows a partial-analysis warning; invalid core analysis shows safe retry guidance without fixture fallback.

The server, not the browser, supplies the user stage, acting participant, required and optional item sets, active clarification, and next-action label. Required issues are deterministically ordered by scope, amount and price coverage, materials, timing, payment, then other critical responsibility. Within a category, stable agreement-item order breaks ties. Equivalent clarification targets are deduplicated with a deterministic fingerprint, so retries do not create competing questions.

Conflicting and critical one-sided meanings require attention. They can be resolved or explicitly carried forward as unresolved; absence of a click is never treated as consent. A `not_discussed` topic is optional unless the server classifies it as critical. Optional details are grouped for later review and may be discussed in one deliberate batch, proposed not applicable, or left visibly not discussed. Neither a missing statement nor a unilateral not-applicable proposal becomes alignment.

Every successful analysis remains an immutable internal event. A user-facing Agreement Map version advances only when its semantic fingerprint changes. The fingerprint covers normalized item state, participant positions and statuses, an evidence-bearing transition from missing to stated, and mutually acknowledged not-applicable treatment; it excludes neutral-summary wording, record IDs, timestamps, and provider metadata. This preserves provenance without presenting retries or wording-only differences as meaningful new versions.

Clarifications target the exact validated item. A one-sided issue asks only the participant who has not stated a position; a direct conflict collects separate answers from both people and hides the first until the second is submitted. Re-analysis preserves every internal snapshot, while the primary UI shows only a concise update when meaning changes.

Homeowner and Electrician then review sequentially on the same device and explain the critical terms in their own words. Partial or insufficient teach-back receives a focused follow-up; contradiction reopens the exact affected term. After two matching teach-backs, each participant separately confirms the same version and unresolved-item list. The resulting receipt preserves aligned and unresolved categories and clearly states that it is not a legal contract.

## Progressive Disclosure and Usability Criteria

The default view uses non-technical labels, one primary action, short explanations, and a five-stage progress indicator. Exact evidence, item keys, prior internal events, optional topics, and integrity details remain available through clearly labelled disclosures. The first useful click on each screen must either advance the server-owned workflow, open the exact evidence or issue needed for that decision, or return safely to the previous summary. It must never expose an unrelated form, duplicate a clarification, submit on navigation, or imply that an unresolved item was agreed.

At the supported desktop, tablet, and mobile widths, the primary action must appear without horizontal scrolling, keyboard focus must remain visible through handoff and error controls, loading must prevent duplicate submission, and a missing in-memory session must offer a truthful restart path. These are release criteria; broader moderated usability research remains planned.

## Status

**Implemented:** deterministic English demo and receipt; the guided five-stage English Live flow; server-derived next actions; deterministic issue priority and clarification deduplication; required-versus-optional issue handling; immutable internal analysis events with meaningful map versions; OpenAI Structured Outputs for analysis and teach-back; same-device participant handoff; separate confirmations; original evidence; safe errors; and Live clarity receipt.

**Partially implemented:** independent English/Hindi language fields and a translation boundary; Hindi remains disabled. Same-device handoff hides earlier teach-back in the ordinary UI but is not authentication or strong privacy.

**Planned:** moderated usability validation, audio with explicit recording consent, Hindi and translation, QR/separate-device joining, realtime updates, authentication, durable persistence/recovery, retention controls, identity verification, and custom PDF output. A MeaningSync clarity receipt records stated understanding; it is not legal advice, an electronic signature, or a legally enforceable contract.
