# Conversation-First Manual Test Plan

## Setup and Joining

- Apply Alembic migrations and start FastAPI/Next.js with explicit local origins. Do not enable paid OpenAI tests.
- Verify Preferences and Participation display exactly six progress steps, English defaults, Live INR/USD/EUR choices, either creator role, and shared/separate modes.
- Create a separate-device session. Confirm the invite belongs to the opposite role, QR/copy fallback works, and no fragment secret is displayed.
- Join with one action; verify the fragment disappears and both devices automatically enter Conversation.
- Check used/expired/replaced/malformed invites, refresh recovery, and backend restart.

## Conversation and Decisions

- Verify each separate device sends only its role’s messages; shared mode can switch roles visibly.
- Confirm both must speak and mark ready, only the creator compares, and any new message clears both readiness indicators.
- Use a mocked analyzer or Demo; never make a paid request. Verify the loading state, Matches / Needs a decision / Not discussed sections, and evidence for all non-missing terms.
- Submit one private choice and verify it remains hidden. Test compatible choices, different choices without immediate repeat, Discuss again, Leave unresolved, and optional missing topics.
- Confirm there is no mandatory teach-back question.

## Confirmation and Receipt

- Confirm separately as both roles. Request a change and verify Conversation focus, readiness reset, and confirmation invalidation.
- Issue the receipt only after both reconfirm the same version. Verify roles, languages, session currency, original evidence currency, timestamps, history, unresolved/missing terms, hash, and disclaimer.

## Responsive and Accessibility

Inspect all six steps at 1440×900, 1024×768, and 390×844. Check keyboard focus, labels, contrast, status text, no clipped content/horizontal page overflow, usable actions, and no console or hydration errors.
