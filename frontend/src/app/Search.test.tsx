import {fireEvent, render, screen} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {describe, expect, it, vi} from "vitest";

import {I18nProvider} from "@/i18n";

// QA 2026-10-07 rank 3: on a first visit the city list arrives seconds after the page; until then the only row was
// "Add 'Motijheel' as a city", which a person (and the check) picked before any place could be offered.
const state = {loading: true, city: null as any};
vi.mock("@/lib/city", async (orig) => ({...(await orig<typeof import("@/lib/city")>()), useCity: () => ({cities: [], city: state.city, setCity: () => undefined, loading: state.loading, error: null, reload: () => undefined})}));
vi.mock("@/lib/places", () => ({usePlaceSuggestions: () => ({places: [], searching: false})}));
import {Search} from "./Search";

const typeIn = () => {
  render(<MemoryRouter><I18nProvider><Search /></I18nProvider></MemoryRouter>);
  fireEvent.change(screen.getByRole("combobox"), {target: {value: "Motijheel"}});
};

describe("go-anywhere search while the city list is loading", () => {
  it("says it is searching and does not offer to add the typed name as a city", () => {
    state.loading = true; typeIn();
    expect(screen.queryByText(/as a city/)).toBeNull();
    expect(screen.getByRole("listbox").textContent).toMatch(/search/i);
  });

  it("offers to add it once the list has loaded and nothing matched", () => {
    state.loading = false; typeIn();
    expect(screen.getByText(/as a city/)).toBeInTheDocument();
    expect(screen.getByRole("option").textContent).toBe('Add "Motijheel" as a city');   // QA rank 13: it read "add Add …"
  });
});
