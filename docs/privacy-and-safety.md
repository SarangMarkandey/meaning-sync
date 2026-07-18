# Privacy and Safety

## Data Flow

The browser sends speaker-attributed English text to FastAPI through the typed JSON client. Only FastAPI can call OpenAI, and only the creator’s explicit readiness-gated **Compare what we mean** action starts Live analysis. Messages, readiness, joining, choices, confirmation, polling, and receipt generation are deterministic and make no model call. Demo Mode and normal automated tests are key-free/mocked.

Do not put API keys, authorization headers, invitation fragments, prompts, model reasoning, raw provider errors, or full conversations in routine logs. Keep backend secrets in ignored `.env` files and use explicit CORS origins.

## Durable Live Storage

Live sessions retain participants, creator role, session currency, readiness, messages, immutable versions, questions/private selections, confirmations, request digests, and receipts in validated versioned SQL state until configured expiry. Original evidence retains its stated language and currency. Demo remains process-local. Automatic cleanup, backup governance, and user-controlled deletion are not implemented.

## Role Authorization

Each Live request after creation requires an expiring bearer credential bound to one session and role. Only SHA-256 hashes are stored. A separate-device creator receives only their credential; the opposite role receives an expiring, single-use invitation claimed atomically. QR generation is local, the join page removes the URL fragment, and credentials stay in `sessionStorage`. Either Customer or Service provider may create.

The first private choice is withheld from all participant-scoped responses until every addressed person answers. This prevents accidental ordinary-flow disclosure, not a compromised browser, credential, or database.

## Limitations and Receipt

Shared-device switching is presentation, not authentication. Separate-device credentials authorize possession, not identity. Neither path proves comprehension, freely given consent, or authorship. New conversation text or a requested change clears readiness and invalidates current confirmations.

The immutable receipt preserves matching, unresolved, one-sided, and not-discussed terms, evidence, history, roles/languages/currency, timestamps, and a SHA-256 integrity hash. The hash is not a signature, trusted timestamp, identity proof, or legal guarantee. MeaningSync does not provide legal advice, and its receipt is not a legal contract.
