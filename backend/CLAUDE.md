# Backend notes

FastAPI + SQLModel + SQLite. See root [CLAUDE.md](../CLAUDE.md) for the full picture.

- Layout: `app/routers`, `app/services`, `app/repositories`, `app/clients` (Nominatim,
  OSRM, Transitous, Open-Meteo, LLM), `app/models.py` (SQLModel tables), `app/schemas.py` (Pydantic
  request/response DTOs, kept separate from DB models).
- Routers call services, never the DB. Trips: the router gets a `TripService` via
  `Depends(...)`, which gets its `TripRepository` the same way (unit-testable with a fake
  repository). Comparison, recommendation and geocoding services are plain functions the
  routers call directly; they use clients, not the DB.
- All external HTTP calls (Nominatim/OSRM/Transitous/Open-Meteo/OpenAI) go through `app/clients/*`, each
  with a short timeout and a typed return value — never call `httpx`/`requests` directly
  from a service.
- Nominatim usage policy requires a real `User-Agent` identifying the app, set via
  `app/clients/nominatim.py` config, not a browser-spoofing string.
- SQLite file lives under a Docker named volume in prod, local file in dev — path comes
  from `DATABASE_URL` env var, never hardcoded.
- `pytest` for tests, `ruff` for lint/format. Run both before considering a feature done.
- `/health` returns 200 with no DB/external dependency — used for container healthchecks.
