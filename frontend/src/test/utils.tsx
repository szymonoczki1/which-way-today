import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import type { Trip } from "../lib/types";

/** Fresh QueryClient per test; retry off so error states render immediately. */
export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  // As a wrapper (not wrapping ui directly) so rerender() keeps the provider.
  return {
    client,
    ...render(ui, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    }),
  };
}

export function makeTrip(overrides: Partial<Trip> = {}): Trip {
  return {
    id: 1,
    name: "Home -> Uni",
    origin_address: "Gdansk Main Station",
    origin_lat: 54.355,
    origin_lon: 18.646,
    destination_address: "Gdansk University of Technology",
    destination_lat: 54.371,
    destination_lon: 18.613,
    usual_departure_time: "08:00:00",
    ...overrides,
  };
}
