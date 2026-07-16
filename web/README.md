# MeaningSync Web

Next.js 16, React, TypeScript, Tailwind, and Vitest power the MeaningSync frontend.

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`. Open `http://localhost:3000` and choose the deterministic demo or English live-text preview.

Useful checks:

```bash
npm run lint
npm run type-check
npm test
npm run build
```

All backend calls go through `src/lib/api.ts`. Never add an OpenAI key or direct OpenAI request to frontend code. Live results with `status: "partial"` keep the agreement map and evidence visible, omit an unsafe clarification, and show the backend warning separately from hard request errors. Implemented routes are `/`, `/demo/setup`, `/demo`, `/live/setup`, and `/live`. Hindi, audio, separate devices, and a live clarity receipt remain planned. MeaningSync does not provide legal advice.
