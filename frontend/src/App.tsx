import { lazy, Suspense, useEffect, useRef, useState } from "react";

import { ComparisonPanel } from "./features/comparison/ComparisonPanel";
import { useComparison } from "./features/comparison/queries";
import { RecommendationCard } from "./features/comparison/RecommendationCard";
import { BackendStatus } from "./features/health/BackendStatus";
import { AddTripForm } from "./features/trips/AddTripForm";
import { useTrips } from "./features/trips/queries";
import { TripList } from "./features/trips/TripList";

const RouteMap = lazy(() => import("./features/trips/RouteMap"));

function App() {
  // Only the *selection* is local UI state; trip data itself lives in TanStack Query.
  const [selectedTripId, setSelectedTripId] = useState<number | null>(null);
  const detailsRef = useRef<HTMLElement>(null);
  // Bumped on every pick (even of the already-selected trip), so a phone user who
  // scrolled back up to the list is taken to the details again.
  const [scrollRequest, setScrollRequest] = useState(0);
  const selectTrip = (tripId: number | null) => {
    setSelectedTripId(tripId);
    if (tripId !== null) setScrollRequest((n) => n + 1);
  };
  const trips = useTrips();
  const selectedTrip = trips.data?.find((trip) => trip.id === selectedTripId);
  // Same query key as inside ComparisonPanel, so this is one request, shared.
  const comparison = useComparison(selectedTrip?.id ?? null);

  // On phones the details sit below the form and list; bring them into view
  // when a trip is picked. On wide screens they're already beside the list.
  const shownTripId = selectedTrip?.id;
  useEffect(() => {
    if (shownTripId === undefined) return;
    if (window.matchMedia?.("(max-width: 767px)").matches) {
      detailsRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [shownTripId, scrollRequest]);

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
          <AddTripForm onCreated={selectTrip} />
          <TripList selectedTripId={selectedTripId} onSelect={selectTrip} />
        </section>

        <section
          ref={detailsRef}
          aria-labelledby="comparison-heading"
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 id="comparison-heading" className="font-medium">
            {selectedTrip ? selectedTrip.name : "Comparison"}
          </h2>
          {selectedTrip ? (
            <Suspense
              fallback={<p className="text-sm text-slate-500">Loading map…</p>}
            >
              <RouteMap trip={selectedTrip} routes={comparison.data?.options} />
            </Suspense>
          ) : (
            <p className="text-sm text-slate-500">
              Select a trip to see its route and compare ways to get there.
            </p>
          )}
          {selectedTrip && <RecommendationCard tripId={selectedTrip.id} />}
          {selectedTrip && <ComparisonPanel tripId={selectedTrip.id} />}
        </section>
      </main>
    </div>
  );
}

export default App;
