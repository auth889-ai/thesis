import {render, screen} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {describe, expect, it} from "vitest";

import {I18nProvider} from "@/i18n";
import {LeaveWhen} from "./LeaveWhen";

// QA 2026-10-07 rank 10: the everyday Leave when panel showed "REAL — OpenStreetMap geometry converted by SUMO netconvert" and
// "every section driven at its map speed limit; no traffic, signals or queues". Those belong on Research (plain language rule).
const trip: any = {city_id: "dhaka", available: true, length_m: 2500, sections: Array(46).fill({}), traffic: "none",
  network: {source: "REAL — OpenStreetMap geometry converted by SUMO netconvert", limits: "x"},
  at_limits: {value: 2.9, unit: "min", tag: {kind: "simulated", basis: "every section driven at its map speed limit; no traffic, signals or queues", calibrated_to: "uncalibrated"}}};
const city: any = {id: "dhaka", display_name: {en: "Dhaka", bn: "ঢাকা"}, units: {distance: "km"}};

describe("Leave when on an everyday page", () => {
  it("says the map-speed time in one plain sentence with its tag and Research link, and no developer wording", () => {
    const {container} = render(<MemoryRouter><I18nProvider><LeaveWhen trip={trip} stop="0" city={city} /></I18nProvider></MemoryRouter>);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/netconvert|SUMO|signals or queues|uncalibrated/i);
    expect(text).toMatch(/About 3 min at the map's speed limits, without traffic\./);
    expect(screen.getByRole("link", {name: /how we know/i})).toHaveAttribute("href", "/lab/references");
  });
});
