# Agreement Analysis

## Boundary

`DeterministicAgreementAnalyzer` powers Demo; `OpenAIAgreementAnalyzer` powers English Live. Both return the same evidence-bearing domain model. Only FastAPI calls OpenAI. Joining, polling, messages, readiness, private choices, confirmation, and receipts never trigger analysis. After both roles have spoken and marked ready, only the session creator can explicitly compare.

## Meaning Contract

Every atomic term has an `analysis_item_key`, topic/facet, neutral summary, participant positions/statuses, original evidence IDs, hydrated evidence, and optional exact decision target. States are:

- `aligned`: both explicitly support compatible meaning;
- `conflicting`: both state incompatible meaning;
- `stated_by_one`: exactly one states the term;
- `not_discussed`: neither states it.

The UI renders Matches, Needs a decision, and Not discussed. Non-missing terms must have evidence. Currency metadata never converts evidence.

## Validation and Versions

Prompt `agreement-analysis-v4` treats participant text as untrusted, rejects invention/silence-based agreement, and separates atomic claims. FastAPI validates participant ownership, evidence, canonical keys, duplicates, and clarification ownership, then hydrates original evidence from the trusted request. Invalid core output is a controlled error; an unusable optional clarification yields a partial valid map.

Every validated comparison creates an immutable internal snapshot. The visible Agreement Map number advances only when a SHA-256 semantic fingerprint changes. Wording, IDs, timestamps, and provider metadata do not advance it. Re-entering Conversation and adding text retains prior versions, clears readiness/reviews/confirmations, and requires another explicit comparison.

## Choice-Based Decisions

Only conflicting and one-sided items need decisions. Options are deterministic renderings of recorded positions, plus **Something else** and **I’m not sure**. The first answer remains hidden. Compatible answers may derive a child version; different answers remain unresolved and suppress immediate repetition until people deliberately discuss again. Missing topics are optional. There is no mandatory teach-back or minimum question count.

MeaningSync records stated meaning and selections; it does not prove comprehension or provide legal advice.
