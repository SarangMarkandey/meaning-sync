# Repository Guidelines

## Project Structure & Module Organization

The repository is split into frontend, backend, and documentation areas:

- `web/` contains the Next.js 16 application. Routes, layouts, and global styles live in `web/src/app/`; static assets belong in `web/public/`.
- `api/` is the Python backend scaffold. Add HTTP routes under `api/app/api/`, business rules under `api/app/domain/`, request/response models under `api/app/schemas/`, and integrations or orchestration under `api/app/services/`.
- `api/tests/` contains Pytest API/domain coverage, and `docs/` holds architecture notes and decisions.
- `bwwoai/` is a local virtual environment; do not edit or commit generated environment files.

Keep features close to their owning layer. Keep business logic out of React pages and API handlers.

## Build, Test, and Development Commands

Run frontend commands from `web/`:

- `npm ci` installs the exact dependencies recorded in `package-lock.json`.
- `npm run dev` starts the local development server at `http://localhost:3000`.
- `npm run lint` checks TypeScript and React code with ESLint.
- `npm run build` creates a production build and performs framework/type validation.
- `npm start` serves the completed production build.

Run backend commands from `api/` after installing `.[dev]`:

- `uvicorn app.main:app --reload` serves FastAPI at `http://localhost:8000`.
- `pytest` runs backend tests; `ruff check .` and `ruff format --check .` enforce style.

## Coding Style & Naming Conventions

Use TypeScript with strict typing, two-space indentation, double quotes, and semicolons, matching the existing frontend. Name React components in PascalCase, functions and variables in camelCase, and route folders in lowercase. Prefer the `@/*` alias for imports from `web/src/`. Use Tailwind utility classes for component styling and keep shared theme rules in `src/app/globals.css`. Run `npm run lint` before submitting changes.

For future Python code, use four-space indentation, snake_case modules/functions, PascalCase classes, and type annotations on public interfaces.

## Testing Guidelines

Pytest covers backend state and evidence rules; Vitest with Testing Library covers frontend behavior. Place backend tests in `api/tests/` as `test_<feature>.py` and colocate frontend tests using `<name>.test.tsx`. Run `pytest` in `api/` and `npm test` in `web/`. Add regression tests for state transitions, privacy boundaries, and agreement-map rendering. No numeric coverage threshold is enforced.

## Commit & Pull Request Guidelines

Use concise Conventional Commit subjects such as `feat(web): add agreement form` or `fix(api): validate participant ids`. Keep commits focused. Pull requests should explain the problem and solution, list verification commands, link issues, and include screenshots for UI changes. Never commit `.env*`, credentials, `.next/`, `node_modules/`, or virtual environments.
