import { BackendStatus } from "./features/health/BackendStatus";

function App() {
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
          className="rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 id="trips-heading" className="font-medium">
            Your trips
          </h2>
          {/* Step 7: trip list, add-trip form and route map. */}
          <p className="mt-2 text-sm text-slate-500">
            Saved trips will appear here.
          </p>
        </section>

        <section
          aria-labelledby="comparison-heading"
          className="rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 id="comparison-heading" className="font-medium">
            Comparison
          </h2>
          {/* Step 8: walk / bike / transit / car comparison with weather. */}
          <p className="mt-2 text-sm text-slate-500">
            Select a trip to compare ways to get there.
          </p>
        </section>
      </main>
    </div>
  );
}

export default App;
