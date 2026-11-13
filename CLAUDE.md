# Which Way Today? — Smart Commute Planner

Recruitment-task MVP for the Xelerit Winter Internship. Full-stack, transport-themed.

## What it does

Users save trips (name, origin, destination, optional usual departure time). For a saved
trip, the app compares walk / bike / public transport / car by time, cost, and CO2, then
gives a weather-aware recommendation (e.g. "rain + wind at 8:00 → take the tram, bike
tomorrow"). Logging a trip with a green mode earns eco-points. An AI prompt (optional,
keyless-fallback) turns the comparison + weather into a short structured recommendation.

## Architecture

```
backend/    FastAPI + SQLModel + SQLite. Layers: routers -> services -> repositories,
            plus clients/ for external APIs (Nominatim, OSRM, Open-Meteo, LLM).
frontend/   React + Vite + TypeScript. TanStack Query for server state, Tailwind for
            styling, Leaflet for the map.
```

Backend and frontend are independent deployables talking over HTTP (REST, JSON). CORS is
configured on the backend for local dev (Vite on :5173) and Docker (nginx on :80).

Request flow: `router` (HTTP concerns, status codes) -> `service` (business logic: unit
conversion, scoring, orchestrating external API clients) -> `repository` (SQLModel
queries). Routers never touch the DB session directly; services never import FastAPI
types. This keeps business logic testable without spinning up HTTP.

## Commands

Backend (run from `backend/`):
- `uvicorn app.main:app --reload` — run the API on :8000
- `pytest` — run tests
- `ruff check . && ruff format .` — lint + format
- `pytest --cov=app` — coverage (optional, nice to have)

Frontend (run from `frontend/`):
- `npm run dev` — Vite dev server on :5173
- `npm run build` — production build
- `npm run lint` — ESLint

Docker (run from repo root):
- `docker compose up --build` — backend on :8000, frontend on :5173

## Conventions

- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`), small and scoped to
  one feature/step at a time.
- **Keep `backend/Dockerfile` and `frontend/Dockerfile` in sync whenever dependencies
  change** (requirements.txt / package.json). Docker is tested against a fresh clone
  before submission, not just local `uv`/`npm` state.
- **The app must work with zero configuration and no AI API key.** If `OPENAI_API_KEY`
  (or equivalent) is unset, the recommendation service falls back to a deterministic
  rule-based recommendation. Never make the AI key a hard dependency for any endpoint.
- External APIs (Nominatim, OSRM, Open-Meteo) are free/keyless but rate-limited and
  sometimes flaky — always have a documented static fallback (e.g. static CO2/cost
  factors for public transport) and handle timeouts gracefully, don't let one slow
  upstream call hang an endpoint.
- Nominatim requires a descriptive `User-Agent` header — see `backend/CLAUDE.md`.
- No premature abstraction: this is an MVP under a hard deadline. Prefer three similar
  lines over a speculative helper used once.

## Env vars

See `.env.example` at repo root. Copied to `.env` (gitignored) for local/Docker runs.
Key ones: `VITE_API_URL` (frontend -> backend base URL), `OPENAI_API_KEY` (optional,
enables LLM recommendations instead of the rule-based fallback).
