import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

function renderApp() {
  // retry: false so error states show immediately instead of after retries.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("App shell", () => {
  it("renders the title and placeholder sections", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(Response.json({ status: "ok" })),
    );

    renderApp();

    expect(
      screen.getByRole("heading", { level: 1, name: /which way today/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /your trips/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /comparison/i }),
    ).toBeInTheDocument();
  });

  it("shows the backend as connected when /health responds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(Response.json({ status: "ok" })),
    );

    renderApp();

    expect(screen.getByRole("status")).toHaveTextContent(/checking/i);
    expect(await screen.findByText(/backend connected/i)).toBeInTheDocument();
  });

  it("shows the backend as offline when /health fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    renderApp();

    expect(await screen.findByText(/backend offline/i)).toBeInTheDocument();
  });
});
