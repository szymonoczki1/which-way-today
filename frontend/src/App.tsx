import { lazy, Suspense, useState } from "react";

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
  const trips = useTrips();
  const selectedTrip = trips.data?.find((trip) => trip.id === selectedTripId);
  // Same query key as inside ComparisonPanel, so this is one request, shared.
  const comparison = useComparison(selectedTrip?.id ?? null);

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

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <section
          aria-labelledby="trips-heading"
          className="space-y-4 rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 id="trips-heading" className="font-medium">
            Your trips
          </h2>
          <AddTripForm onCreated={setSelectedTripId} />
          <TripList
            selectedTripId={selectedTripId}
            onSelect={setSelectedTripId}
          />
        </section>

        <section
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
