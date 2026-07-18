# Decisions and Confirmation

## Check Understanding

Check understanding is one agreement-map screen with Matches, Needs a decision, and Not discussed. Matches show evidence and no controls. Not-discussed topics are optional. A conflicting or one-sided item may open one neutral private choice derived from its recorded participant positions, plus **Something else** and **I’m not sure**.

For a two-person decision, Customer and Service provider answer separately. The first selection, semantic value, ID, and optional text remain backend-only until the second answer. Compatible choices may create a new immutable version. Different choices never create agreement and are not immediately repeated; the participants can return to Conversation focused on that item or leave it unresolved. Uncertainty cannot create alignment. No mandatory teach-back questions are added.

## Conversation Re-entry

**Discuss again** returns the session to Conversation with the selected item identified. **I need to change something** at confirmation does the same. Re-entry and every new message clear both readiness flags, active reviews, and current confirmations. Participants must speak/ready again, and only the creator can explicitly compare the revised conversation.

## Separate Confirmation

Confirmation shows a compact summary of agreed and still-open items. Each participant confirms the same current agreement-version ID separately. In shared-device mode the UI uses a handoff; separate-device controls are restricted to the bearer role. One record can never stand in for both.

A confirmation binds participant, version, acknowledged open items, language, request ID, and timestamp. New text, re-entry, or a child version invalidates current confirmations. Receipt issuance requires two active confirmations of one current version. Confirmation records a stated review; it is not identity verification, consent proof, an electronic signature, or proof of comprehension.
