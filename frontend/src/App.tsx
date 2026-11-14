import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { toRouteQuery, type TripInput } from "./lib/types";

import { ComparisonPanel } from "./features/comparison/ComparisonPanel";
import { useComparison } from "./features/comparison/queries";
import { RecommendationCard } from "./features/comparison/RecommendationCard";
import { BackendStatus } from "./features/health/BackendStatus";
import { AddTripForm } from "./features/trips/AddTripForm";
import { useTrips } from "./features/trips/queries";
import { TripList } from "./features/trips/TripList";
import { UnsavedRouteBanner } from "./features/trips/UnsavedRouteBanner";

const RouteMap = lazy(() => import("./features/trips/RouteMap"));

function App() {
  // Only the *selection* is local UI state; trip data itself lives in TanStack Query.
  // Shown on the right: a saved trip, or a route checked without saving (its
  // looked-up coordinates are kept here so saving it needs no second lookup).
  const [selectedTripId, setSelectedTripId] = useState<number | null>(null);
  const [checkedRoute, setCheckedRoute] = useState<TripInput | null>(null);
  // Bumped on every check, so the save banner starts fresh each time (even when
  // the same coordinates are checked again with a different name).
  const [checkCount, setCheckCount] = useState(0);
  const detailsRef = useRef<HTMLElement>(null);
  // Bumped on every pick (even of the already-selected trip), so a phone user who
  // scrolled back up to the list is taken to the details again.
  const [scrollRequest, setScrollRequest] = useState(0);
  const selectTrip = (tripId: number | null) => {
    setSelectedTripId(tripId);
    // Clearing the trip selection (e.g. the selected trip was deleted) leaves a
    // checked route alone; picking a trip replaces it.
    if (tripId !== null) {
      setCheckedRoute(null);
      setScrollRequest((n) => n + 1);
    }
  };
  const showRoute = (route: TripInput) => {
    setSelectedTripId(null);
    setCheckedRoute(route);
    setCheckCount((n) => n + 1);
    setScrollRequest((n) => n + 1);
  };
  const trips = useTrips();
  const selectedTrip = trips.data?.find((trip) => trip.id === selectedTripId);
  const routeQuery = checkedRoute ? toRouteQuery(checkedRoute) : null;
  const routeName = checkedRoute
    ? checkedRoute.name ||
      `${checkedRoute.origin_address} → ${checkedRoute.destination_address}`
    : "";
  // What the map, recommendation and comparison show (saved trip wins).
  const shown =
    selectedTrip ?? (checkedRoute && { ...checkedRoute, name: routeName });
  // Same query key as inside ComparisonPanel, so this is one request, shared.
  const comparison = useComparison(selectedTrip?.id ?? routeQuery);

  // On phones the details sit below the form and list; bring them into view
  // when a trip is picked. On wide screens they're already beside the list.
  const shownKey = selectedTrip
    ? `trip-${selectedTrip.id}`
    : routeQuery && JSON.stringify(routeQuery);
  useEffect(() => {
    if (!shownKey) return;
    if (window.matchMedia?.("(max-width: 767px)").matches) {
      detailsRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [shownKey, scrollRequest]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-4">
          <div>
            <h1 className="text-xl font-semibold">Which Way Today?</h1>
            <p className="text-sm text-slate-500">
              Walk, bike, tram or car: pick the best way for your commute.
            </p>
          </div>
          <BackendStatus />
        </div>
      </header>

      {/* minmax(0,1fr) on phones too: a plain 1-column grid sizes to its widest
          unwrappable content (e.g. a truncated route) and overflows the screen. */}
      <main className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-6 px-4 py-6 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <section
          aria-labelledby="trips-heading"
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 id="trips-heading" className="font-medium">
            Your trips
          </h2>
          <AddTripForm onCreated={selectTrip} onChecked={showRoute} />
          <TripList selectedTripId={selectedTripId} onSelect={selectTrip} />
        </section>

        <section
          ref={detailsRef}
          aria-labelledby="comparison-heading"
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 id="comparison-heading" className="font-medium">
            {shown ? shown.name : "Comparison"}
          </h2>
          {checkedRoute && !selectedTrip && (
            <UnsavedRouteBanner
              // Fresh name field for each newly checked route.
              key={checkCount}
              route={checkedRoute}
              defaultName={routeName}
              onSaved={selectTrip}
            />
          )}
          {shown ? (
            <Suspense
              fallback={<p className="text-sm text-slate-500">Loading map…</p>}
            >
              <RouteMap trip={shown} routes={comparison.data?.options} />
            </Suspense>
          ) : (
            <p className="text-sm text-slate-500">
              Select a trip to see its route and compare ways to get there.
            </p>
          )}
          {selectedTrip && <RecommendationCard tripId={selectedTrip.id} />}
          {selectedTrip && <ComparisonPanel tripId={selectedTrip.id} />}
          {!selectedTrip && routeQuery && (
            <>
              <RecommendationCard route={routeQuery} />
              <ComparisonPanel route={routeQuery} />
            </>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
