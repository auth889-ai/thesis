import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";

import {I18nProvider} from "@/i18n";
import {api} from "./api";
import {CityProvider, useCity} from "./city";

const dhaka = {id: "dhaka", display_name: {en: "Dhaka"}, country: "BD", center: [90.4, 23.8], bounding_box: [23.7, 90.3, 23.9, 90.5], time_zone: null, default_languages: ["bn"], emergency_numbers: null, units: null, plugins: [], datasets: [], default: true};
const berlin = {...dhaka, id: "berlin", display_name: {en: "Berlin"}, default: false};

function Probe() {
  const {city, cities, error, loading} = useCity();
  return <div><span data-testid="city">{city?.id ?? "none"}</span><span data-testid="n">{cities.length}</span><span data-testid="error">{error ?? ""}</span><span data-testid="loading">{String(loading)}</span></div>;
}
const mount = () => render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><I18nProvider><CityProvider><Probe /></CityProvider></I18nProvider></QueryClientProvider>);

describe("a fresh visitor's city", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); try { localStorage.removeItem("tt.cityId"); } catch { /* no storage here */ } });

  it("gets the default city with nothing stored in the browser", async () => {
    vi.spyOn(api, "cities").mockResolvedValue({configured: [berlin, dhaka], problems: {}});
    mount();
    await waitFor(() => expect(screen.getByTestId("city").textContent).toBe("dhaka"));
    expect(screen.getByTestId("n").textContent).toBe("2");
    expect(screen.getByTestId("error").textContent).toBe("");
  });

  it("is told why when the list cannot be loaded, instead of loading forever", async () => {
    vi.spyOn(api, "cities").mockRejectedValue(new Error("HTTP 500"));
    mount();
    await waitFor(() => expect(screen.getByTestId("error").textContent).toContain("500"), {timeout: 5000});   // the provider retries once before it gives up
    expect(screen.getByTestId("city").textContent).toBe("none");
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });

  it("is told when the server lists no city at all", async () => {
    vi.spyOn(api, "cities").mockResolvedValue({configured: [], problems: {dhaka: "ValidationError: not_a_field"}});
    mount();
    await waitFor(() => expect(screen.getByTestId("error").textContent).toContain("ValidationError"));
  });
});
