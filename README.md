# Which Way Today?

A commute planner: enter a trip and see whether to **walk, cycle, take public transport
or drive**, compared by time, cost and CO₂, with a recommendation based on the **weather
forecast for when you leave**.

![Desktop view](docs/screenshot-desktop.png)

**Demo video:** [docs/demo.mp4](docs/demo.mp4)

## Features

- **Check a route** without saving it, or **save trips** you make regularly (with an
  optional usual departure time).
- **Compare four modes:** real street routes for walking, cycling and driving, and a real
  public transport journey from timetables (e.g. *🚶 3 min → 🚋 Tram 6 · 9 min → 🚶 9 min,
  leaves 08:04*), all drawn on a map.
- **Weather-aware recommendation:** uses the forecast for your departure time, rules out
  modes that don't make sense (too long, too wet, too windy, icy) and picks the greenest
  reasonable one.
- **Optional AI:** with an OpenAI key, a model makes the final choice and explains it;
  without one, the app uses its rules.
- **Honest numbers:** estimates are marked `~`, and a price is shown only when it's
  known.

## Running locally

No configuration or API key needed.

**Requirements:** Python 3.12, Node.js 22.12+ or 24.

**1. API**: from the repo root:

```bash
cd backend
python3.12 -m venv .venv          # Windows: py -3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload      # http://localhost:8000 (docs: /docs)
```

**2. Frontend**: in a second terminal, from the repo root:

```bash
cd frontend
npm ci
npm run dev                        # http://localhost:5173
```

**3.** Open <http://localhost:5173> and check a route, e.g. `Gdańsk Główny` →
`Politechnika Gdańska` at `08:00`.

**Or with Docker:** `docker compose up --build` (same addresses).

**Tests:** `pytest` in `backend/` (185 tests), `npm test` in `frontend/` (127 tests).

Optional settings are in [`.env.example`](.env.example) (e.g. `OPENAI_API_KEY`).

## Technical description

| | |
|---|---|
| **Backend** | Python, FastAPI, SQLModel, SQLite |
| **Frontend** | React, TypeScript, Vite, TanStack Query, Tailwind, Leaflet |
| **Data** | Nominatim (addresses), OSRM (routes), Transitous (timetables), Open-Meteo (weather), OpenAI (optional) |
| **Quality** | pytest, Vitest, ruff, oxlint, prettier, Docker |

The backend is split into **routers** (HTTP), **services** (logic), **repositories**
(database) and **clients** (one per external API). The frontend talks to it through a
single typed API client.

**API:** CRUD on `/trips`; `/trips/{id}/comparison` and `/trips/{id}/recommendation`
for a saved trip; `/routes/comparison` and `/routes/recommendation` for an unsaved one;
`/geocode` for addresses. CORS allows the frontend at `localhost:5173`.

**Notable solutions**

- **Fail soft:** the five calls to external services run in parallel under a 6-second
  deadline; if one fails, only that mode falls back to an estimate.
- **Rules first, AI second:** the AI can only choose among modes the rules allow, and
  any invalid answer falls back to the rules. It never sees trip names or addresses.
- **Fair transit times:** counted door to door, including the wait for the first
  vehicle.
- **Compute once:** the comparison and recommendation share one result, so their
  numbers always match.

## How I used AI tools

I built the project with **Claude Code**. It wrote most of the code; I decided what to
build and made the design choices (for example the API shape, real timetable data
instead of estimates, dropping eco-points, adding "check without saving").

Each feature followed the same workflow: plan, **failing tests first**, implementation,
then a **code-review subagent** whose findings I fixed or dismissed. It caught real
bugs, such as walking and cycling routes silently coming back as car routes.

The configuration is committed: [`CLAUDE.md`](CLAUDE.md) (plus
[`backend/`](backend/CLAUDE.md) and [`frontend/`](frontend/CLAUDE.md) versions),
[`AGENTS.md`](AGENTS.md), the [`/feature`](.claude/commands/feature.md) and
[`/review`](.claude/commands/review.md) commands, the
[review subagent](.claude/agents/code-reviewer.md), and
[`settings.json`](.claude/settings.json) (allowed commands and a formatting hook).
