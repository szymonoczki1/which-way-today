# Frontend notes

React + Vite + TypeScript. See root [CLAUDE.md](../CLAUDE.md) for the full picture.

- API base URL comes from `VITE_API_URL` (see `.env.example`), never hardcoded — read it
  once in `src/lib/api.ts`.
- TanStack Query owns all server state (trips, comparisons); no server data in local
  `useState`/Redux. Co-locate query keys with their hook in `src/features/<feature>/`.
- Every data-fetching view handles three states explicitly: loading, empty, error. Don't
  skip the empty state — it's part of the UX grading criteria.
- Tailwind for styling; keep components small and composable rather than one large page
  file.
- Leaflet map is isolated in its own component (`src/features/trips/RouteMap.tsx`) so it
  can be lazy-loaded and doesn't fight React's render cycle (Leaflet mutates the DOM
  directly).
- `npm run lint` (oxlint, from the Vite template; config in `.oxlintrc.json`) and
  `npm test` (Vitest) before considering a feature done.
