# Which Way Today? — Smart Commute Planner

Recruitment-task MVP for the Xelerit Winter Internship. Full-stack, transport-themed.

## What it does

Users save trips (name, origin, destination, optional usual departure time). For a saved
trip, the app compares walk / bike / public transport (real timetable journeys via
Transitous) / car by time, cost, and CO2, then
gives a weather-aware recommendation using the forecast for the departure time (e.g. rain
at 08:00 → take public transport). Deterministic rules decide which modes are suitable; an
optional AI model (OPENAI_API_KEY) picks among those and explains why, with the rules as
the keyless fallback. (Eco-points were in the original plan and were dropped.)

## Architecture

```
backend/    FastAPI + SQLModel + SQLite. Layers: routers -> services -> repositories,
            plus clients/ for external APIs (Nominatim, OSRM, Transitous,
            Open-Meteo, LLM).
frontend/   React + Vite + TypeScript. TanStack Query for server state, Tailwind for
            styling, Leaflet for the map.
```

Backend and frontend are independent deployables talking over HTTP (REST, JSON). CORS is
configured on the backend for the browser origin, `localhost:5173` both in local dev
(Vite) and in Docker (nginx in the container, published on host port 5173).

Request flow: `router` (HTTP concerns, status codes) -> `service` (business logic: unit
conversion, scoring, orchestrating external API clients) -> `repository` (SQLModel
queries). Routers never touch the DB session directly; services never import FastAPI
types. This keeps business logic testable without spinning up HTTP.

## Commands

Backend (run from `backend/`):
- `uvicorn app.main:app --reload` — run the API on :8000
- `pytest` — run tests
- `ruff check . && ruff format .` — lint + format

Frontend (run from `frontend/`):
- `npm run dev` — Vite dev server on :5173
- `npm run build` — production build
- `npm run lint` — oxlint (from the Vite template)
- `npm test` — Vitest
- `npm run format` / `npm run format:check` — prettier (pinned devDependency)

Docker (run from repo root):
- `docker compose up --build` — backend on :8000, frontend on :5173

## Conventions

- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`), small and scoped to
  one feature/step at a time.
- **Keep `backend/Dockerfile` and `frontend/Dockerfile` in sync whenever dependencies
  change** (requirements.txt / package.json). Docker is tested against a fresh clone
  before submission, not just local venv/`npm` state (`scripts/docker-smoke.sh`).
- **The app must work with zero configuration and no AI API key.** If `OPENAI_API_KEY`
  (or equivalent) is unset, the recommendation service falls back to a deterministic
  rule-based recommendation. Never make the AI key a hard dependency for any endpoint.
- External APIs (Nominatim, OSRM, Transitous, Open-Meteo) are free/keyless but
  rate-limited and sometimes flaky — always have a documented static fallback (e.g. the
  public transport estimate when Transitous fails) and handle timeouts gracefully, don't
  let one slow upstream call hang an endpoint.
- Nominatim requires a descriptive `User-Agent` header — see `backend/CLAUDE.md`.
- No premature abstraction: this is an MVP under a hard deadline. Prefer three similar
  lines over a speculative helper used once.

## Env vars

See `.env.example` at repo root. Copied to `.env` (gitignored) for local/Docker runs.
Key ones: `VITE_API_URL` (frontend -> backend base URL), `OPENAI_API_KEY` (optional,
enables LLM recommendations instead of the rule-based fallback).
