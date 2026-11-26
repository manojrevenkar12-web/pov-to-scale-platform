import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import results from "../public/data/results.json";

function mockFetch(...responses: Array<() => Promise<Response>>) {
  const fn = vi.fn();
  responses.forEach((r) => fn.mockImplementationOnce(r));
  vi.stubGlobal("fetch", fn);
  return fn;
}

const ok = (body: unknown) => () => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("dashboard states", () => {
  it("shows skeletons while loading, then the numbers", async () => {
    mockFetch(ok(results));
    const { container } = render(<App />);
    expect(container.querySelector("[data-status='loading']")).not.toBeNull();
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
    await screen.findAllByText("Client-data isolation incidents");
    expect(screen.getByRole("group", { name: "Seed split" })).toBeInTheDocument();
    expect(screen.getAllByText("Platform").length).toBeGreaterThan(0);
  });

  it("explains an error and retries", async () => {
    const fetch = mockFetch(() => Promise.resolve(new Response("nope", { status: 500 })), ok(results));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 500");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findAllByText("Client-data isolation incidents");
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("says how to produce results when there are none", async () => {
    mockFetch(ok({ dev: null, heldout: null }));
    render(<App />);
    expect(await screen.findByText("No lab results yet")).toBeInTheDocument();
  });

  it("switches to a table that carries every number", async () => {
    mockFetch(ok(results));
    render(<App />);
    await screen.findAllByText("Client-data isolation incidents");
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    const table = await screen.findByRole("table");
    expect(table.querySelectorAll("tbody tr").length).toBe(results.dev.metrics.length);
  });
});
