# Clarity Receipt

## Issuance Rules

A Live clarity receipt can be issued only after both participants submit matching teach-backs and separately confirm the same current agreement version, including acknowledgments for every conflicting or one-sided item. A stale version, one confirmation, a mismatched teach-back, or an unfinished review returns a controlled `receipt_not_ready` or version error. Repeating the issue request returns the existing snapshot rather than creating another receipt.

The receipt is a record of stated understanding. It can represent either fully aligned meaning or the same unresolved meaning explicitly acknowledged by both participants. It does not force resolution.

## Snapshot Schema

The frozen `clarity-receipt-v1` snapshot includes:

- receipt and session IDs, agreement-version ID and number, and issue timestamp;
- each participant’s role, display name, and language;
- full evidence-bearing aligned terms;
- conflicting/unresolved, one-sided, and important not-discussed terms in separate categories;
- not-applicable proposals with the proposing participant roles;
- clarification history with source/resulting versions and response message references;
- both matching teach-back completion records;
- both confirmation IDs, languages, and timestamps;
- `fully_aligned` or `contains_unresolved_items` status;
- application/schema versions, disclaimer, and integrity hash.

`fully_aligned` means the final version has no unresolved item keys. Any conflict, one-sided meaning, or not-discussed item produces `contains_unresolved_items`, even when both participants explicitly choose to proceed. A unilateral not-applicable proposal remains a visible proposal and never silently becomes shared agreement.

## Required Disclaimer

> This clarity receipt records the participants’ stated understanding. MeaningSync does not provide legal advice, and this receipt is not presented as a legally enforceable contract.

The receipt view repeats this disclaimer, presents a distinct unresolved-items warning when needed, shows confirmation times and identifiers, and offers Print / Save through normal browser printing. MeaningSync does not generate a custom PDF in this milestone.

Receipt is the fifth and final user stage. Its default view leads with the plain-language aligned/unresolved summary and separate confirmation status. Evidence, clarification history, internal snapshot identifiers, and integrity details remain expandable or secondary. The receipt refers to the meaningful Agreement Map number that both participants reviewed while retaining the exact internal agreement-version ID for provenance.

## Integrity Hash

FastAPI serializes the receipt payload without `integrity_hash` as canonical JSON with sorted keys and compact separators, then stores the lowercase SHA-256 digest. The same canonical payload produces the same digest, so recomputation can detect a changed payload.

This unkeyed hash is not an electronic signature, trusted timestamp, identity proof, authentication mechanism, blockchain record, or guarantee of legal enforceability. It does not prove who used the device. The entire receipt exists only in process memory and disappears after backend restart; durable verification and persistence remain planned.
