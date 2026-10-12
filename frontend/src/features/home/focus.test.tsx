import {QueryClient, QueryClientProvider} from "@tanstack/react-query";
import {fireEvent, render, screen, waitFor} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {beforeEach, describe, expect, it, vi} from "vitest";

import {useEffect} from "react";

import {I18nProvider, useI18n} from "@/i18n";

/** Render in a language through the provider itself (nothing stored). */
function As({lang, children}: {lang: string; children: React.ReactNode}) {
  const {lang: now, setLang} = useI18n();
  useEffect(() => { setLang(lang, false); }, []);                          // eslint-disable-line react-hooks/exhaustive-deps
  return now === lang ? <>{children}</> : null;
}

// the map and the Ferrostar drive need a browser; their own tests cover them
vi.mock("@/features/today/HomeMap", () => ({HomeMap: () => <div data-testid="map" />}));
vi.mock("@/features/today/Navigate", () => ({Navigate: () => <div data-testid="navigate" />}));
vi.mock("@/lib/pack", () => ({savePack: vi.fn(), ZOOMS: [12, 14, 16], ZOOMS_LOW_DATA: [12, 14]}));
const nearest = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return {...real, api: {...real.api, emergencyNearest: (...a: unknown[]) => nearest(...a)}};
});
import {NearestCard} from "./NearestCard";
import {saveForWeakSignal} from "./NavigateCard";
import {SosCard} from "@/features/emergency/SosCard";
import {api} from "@/lib/api";

const dhaka: any = {id: "dhaka", display_name: {en: "Dhaka", bn: "ঢাকা"}, routing: {engine: "valhalla"}, units: {distance: "km"}, emergency_numbers: {ambulance: "999"}};
const wrap = (ui: React.ReactNode, lang = "bn") =>
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><I18nProvider><As lang={lang}>{ui}</As></I18nProvider></MemoryRouter></QueryClientProvider>);
const here = {coords: {latitude: 23.7806, longitude: 90.4078}};

beforeEach(() => {
  (navigator as any).geolocation = {getCurrentPosition: (ok: (p: unknown) => void) => ok(here)};
  nearest.mockReset();
});

describe("the focused Home's three cards (owner, 2026-10-08)", () => {
  it("nearest hospital: the first one large, in Bangla digits, the next two small", async () => {
    nearest.mockResolvedValue({available: true, nearest: [
      {osm_id: "a", name: "Module General Hospital", time_s: 180, distance_m: 400}, {osm_id: "b", name: "General Medical Hospital", time_s: 240, distance_m: 700}, {osm_id: "c", name: "PG Outdoor", time_s: 300, distance_m: 700}]});
    wrap(<NearestCard city={dhaka} />);
    fireEvent.click(screen.getByRole("button", {name: "আমার অবস্থান ব্যবহার করুন"}));
    await waitFor(() => expect(screen.getByText(/Module General Hospital: প্রায় ৩ মিনিট \(০\.৪ কিমি\)/)).toBeInTheDocument());
    expect(screen.getByText(/তারপর PG Outdoor/)).toBeInTheDocument();
    expect(nearest).toHaveBeenCalledWith("dhaka", 23.7806, 90.4078);
  });

  it("nearest hospital: a city without hospital data says so plainly", async () => {
    nearest.mockResolvedValue({available: false, code: "no_hospitals"});
    wrap(<NearestCard city={{...dhaka, id: "los_angeles", display_name: {en: "Los Angeles"}}} />, "en");
    fireEvent.click(screen.getByRole("button", {name: "Use my location"}));
    await waitFor(() => expect(screen.getByText(/No data for Los Angeles/)).toBeInTheDocument());
  });

  it("navigate: Start saves the route answer, the start-up answers and the tiles before the drive", async () => {
    const save = vi.fn().mockResolvedValue({tile_bytes: 1_000_000, api_bytes: 20_000, asset_bytes: 5_000});
    const bytes = await saveForWeakSignal("dhaka", {lat: 23.78, lon: 90.4}, {lat: 23.74, lon: 90.39}, [[90.4, 23.78], [90.39, 23.74]], save);
    expect(bytes).toBe(1_025_000);
    const urls: string[] = save.mock.calls[0][3];
    for (const u of [api.citiesUrl, api.routeUrl("dhaka", "23.78,90.4", "23.74,90.39", "car")]) expect(urls).toContain(new URL(u, location.origin).toString());
  });

  it("crash SOS, compact: the Arm button, and no replays or rule line (those stay on the Emergency page)", () => {
    wrap(<SosCard city={dhaka} compact />, "en");
    expect(screen.getByRole("button", {name: /Arm/})).toBeInTheDocument();
    expect(screen.queryAllByRole("button").filter((b) => /normal ride|hard brake|crash-like jolt/i.test(b.textContent ?? ""))).toEqual([]);
    expect(screen.queryByText(/WreckWatch/)).toBeNull();
  });
});
