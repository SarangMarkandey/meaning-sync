# Clarity Receipt

## Authorized Issuance

Either authorized role may read an issued receipt. Only the session creator—Customer or Service provider—may issue it after both people separately confirm the same current version. Credentials and invitations never enter the receipt payload. Repeated issue requests return the existing immutable snapshot.

## Snapshot Content

The receipt includes:

- receipt/session/version IDs, issue time, and session start time;
- creator role, participant roles, optional self-provided display names, languages, confirmation languages, and confirmation times;
- selected session currency without conversion;
- full evidence-bearing matching terms, retaining original stated currency and audio machine/correction provenance;
- conflicting/unresolved, one-sided, not-applicable, and not-discussed categories;
- immutable agreement history and version provenance;
- `fully_aligned` or `contains_unresolved_items` status;
- required English/Hindi term localizations and their provenance;
- application/schema versions, English/Hindi legal and identity disclaimers, and integrity hash.

Missing and unresolved items remain visible even after both people confirm. Mixed-language sessions show one bilingual receipt; same-language sessions avoid redundant translations. A unilateral not-applicable proposal never becomes shared agreement.

## Required Disclaimer

> MeaningSync Clarity Receipt — not a legal contract.

The fuller receipt text explains that it records stated understanding and is not legal advice or an enforceable contract. It also states in English and Hindi that participant names are self-provided and MeaningSync does not verify identity. Browser printing is available; MeaningSync does not generate a custom PDF.

## Integrity

FastAPI hashes canonical JSON without the `integrity_hash` field using SHA-256. The payload includes stable semantic IDs, required English/Hindi localizations, confirmation bindings, and unresolved status. Recomputing the payload can reveal changes, but the unkeyed hash is not a signature, identity proof, trusted timestamp, blockchain record, or guarantee of consent/comprehension. SQL persistence lasts only until configured expiry.
