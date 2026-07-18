# Clarity Receipt

## Authorized Issuance

Either authorized role may read an issued receipt. Only the session creator—Customer or Service provider—may issue it after both people separately confirm the same current version. Credentials and invitations never enter the receipt payload. Repeated issue requests return the existing immutable snapshot.

## Snapshot Content

The receipt includes:

- receipt/session/version IDs, issue time, and session start time;
- creator role, participant roles, display labels, languages, and confirmation times;
- selected session currency without conversion;
- full evidence-bearing matching terms, retaining original stated currency;
- conflicting/unresolved, one-sided, not-applicable, and not-discussed categories;
- immutable agreement history and version provenance;
- `fully_aligned` or `contains_unresolved_items` status;
- application/schema versions, disclaimer, and integrity hash.

Missing and unresolved items remain visible even after both people confirm. A unilateral not-applicable proposal never becomes shared agreement.

## Required Disclaimer

> MeaningSync Clarity Receipt — not a legal contract.

The fuller receipt text explains that it records stated understanding and is not legal advice or an enforceable contract. Browser printing is available; MeaningSync does not generate a custom PDF.

## Integrity

FastAPI hashes canonical JSON without the `integrity_hash` field using SHA-256. Recomputing the payload can reveal changes, but the unkeyed hash is not a signature, identity proof, trusted timestamp, blockchain record, or guarantee of consent/comprehension. SQL persistence lasts only until configured expiry.
