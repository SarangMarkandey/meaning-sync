# MeaningSync Product Specification

## Problem

People can leave the same service conversation with different understandings of scope, price, materials, timing, or follow-up work. MeaningSync exposes shared meaning, contradictions, and omissions using the participants’ own statements. It is not primarily a translation product, does not provide legal advice, and produces a clarity receipt rather than a legally enforceable contract.

## Intended Experience

MeaningSync supports agreements where both participants use English, both use Hindi, or each uses a different language. Translation may make cross-language display possible, but agreement intelligence remains the core capability.

The agreement map has three sections:

- **Confirmed:** both participants share the same meaning.
- **Needs clarification:** their stated meanings conflict.
- **Not discussed:** required topics lack evidence.

A neutral question targets each conflict. Participants answer separately; the first answer stays hidden until both respond. Each participant then confirms a teach-back. The final clarity receipt preserves confirmed, unresolved, and missing terms.

The implemented journey is:

`Homepage → Demo language setup → Demo conversation → Agreement map → Clarification → Separate confirmations → Clarity receipt`

The homepage stays focused on the product promise and mode navigation. Selecting **Try Demo** opens `/demo/setup`, where homeowner and electrician languages are stored independently. Both default to English. Language selectors and availability messaging do not appear on the homepage.

## Modes and Status

**Implemented:** Demo Mode with a prepared English ↔ English homeowner/electrician conversation, deterministic analysis, original evidence, private clarification, separate confirmation, and clarity receipt.

**Partially implemented:** independent `en`/`hi` participant settings, original/translated message fields, and an optional translation boundary. The setup screen shows Hindi as coming soon and prevents unsupported sessions from starting. Hindi experiences do not yet have a real translation provider or complete UI.

**Planned:** Live Mode with speech, separate-device session participation, QR joining, durable storage, backend OpenAI analysis, Hindi ↔ Hindi, English ↔ Hindi, and bilingual receipts. The landing page exposes Live Mode only as a future milestone.
