import {describe, expect, it} from "vitest";

import {AMBULANCE_COLOUR, archetype, between, colours, EXTRA, PALETTES, signalColour, vehicleFeatures, WAY_COLOUR, type LiveVehicle} from "./vehicleShapes";

const car: LiveVehicle = [90.4, 23.75, 36, 0, "veh7", 90, "passenger"];

describe("vehicle shapes", () => {
  it("draws a class with its own shape and keeps unknown classes as cars", () => {
    expect([archetype("bus"), archetype("motorcycle"), archetype("cng_autorickshaw"), archetype("passenger"), archetype("something")]).toEqual(["bus", "bike", "auto", "car", "car"]);
  });

  it("draws the class names of a city's vehicle mix with the nearest of the four shapes", () => {
    expect(["Car_Micro", "Motor_Cycle", "CNG", "Rickshaw", "Bus_Minibus", "Pickup_Truck", "Van", "Ambulance", "Special_Purpose", "Bicycle"].map(archetype))
      .toEqual(["car", "bike", "auto", "auto", "bus", "bus", "car", "car", "bus", "bike"]);
  });

  it("turns a vehicle into closed boxes behind its front bumper, pointing along its heading", () => {
    const boxes = vehicleFeatures(car);
    expect(boxes.length).toBe(2);
    for (const b of boxes) {
      const ring = b.geometry.coordinates[0];
      expect(ring.length).toBe(5);
      expect(ring[0]).toEqual(ring[4]);
      expect(b.properties.height).toBeGreaterThan(b.properties.base);
      expect(Math.max(...ring.map((p) => p[0]))).toBeLessThanOrEqual(90.4 + 1e-9);      // heading east: nothing ahead of the bumper
    }
    const lons = boxes[0].geometry.coordinates[0].map((p) => p[0]), lats = boxes[0].geometry.coordinates[0].map((p) => p[1]);
    const lengthM = (Math.max(...lons) - Math.min(...lons)) * 111_320 * Math.cos((23.75 * Math.PI) / 180), widthM = (Math.max(...lats) - Math.min(...lats)) * 111_320;
    expect(lengthM).toBeCloseTo(4.2, 1);
    expect(widthM).toBeCloseTo(1.75, 1);
    expect(boxes[0].properties.colour).toBe(vehicleFeatures(car)[0].properties.colour);     // the same vehicle keeps its colour
  });

  it("glides between two readings and does not invent a vehicle that has left", () => {
    const next: LiveVehicle[] = [[90.402, 23.75, 40, 0, "veh7", 90, "passenger"], [90.5, 23.8, 10, 0, "new", 0, "bus"]];
    const mid = between([car], next, 0.5);
    expect(mid[0][0]).toBeCloseTo(90.401, 6);
    expect(mid[1]).toEqual(next[1]);
    expect(between([car], [], 0.5)).toEqual([]);
    expect(between([car], next, 1.2)).toBe(next);
  });

  it("gives meaning to two colours only in an ambulance run: the ambulance, and a vehicle making way", () => {
    const amb: LiveVehicle = [90.4, 23.75, 50, 0, "ambulance_alert", 0, "emergency"], way: LiveVehicle = [90.4, 23.75, 5, 1, "veh7", 90, "passenger"];
    expect(archetype("emergency")).toBe("ambulance");
    expect(vehicleFeatures(amb, true).every((b) => b.properties.colour === AMBULANCE_COLOUR)).toBe(true);
    expect(vehicleFeatures(way, true)[0].properties.colour).toBe(WAY_COLOUR);
    expect(vehicleFeatures(way)[0].properties.colour).not.toBe(WAY_COLOUR);              // outside an ambulance run the flag colours nothing
    expect(colours("car")).not.toContain(WAY_COLOUR);
  });

  it("reads a signal head's colour from SUMO's phase string", () => {
    expect([signalColour("GrYy", 0), signalColour("GrYy", 1), signalColour("GrYy", 2), signalColour(undefined, 0), signalColour("G", 5)]).toEqual(["#2e9e4f", "#c8322b", "#e0a81c", "#8a8f96", "#8a8f96"]);
  });

  it("keeps the reference's colours apart from the added ones and paints a vehicle from its id only", () => {
    expect(colours("car")).toEqual([...PALETTES.car, ...EXTRA.car]);
    expect(new Set(colours("car")).size).toBe(colours("car").length);
    const slow: LiveVehicle = [90.4, 23.75, 2, 1, "veh7", 10, "passenger"];
    expect(vehicleFeatures(slow)[0].properties.colour).toBe(vehicleFeatures(car)[0].properties.colour);      // speed, heading and equipment change nothing
  });
});
