import {describe, expect, it} from "vitest";

import {MAX_PITCH, MIN_PITCH, NIGHT, ORBIT_DEG_PER_S, orbitBearing, rideWith, STREET} from "./camera";
import type {LiveVehicle} from "./vehicleShapes";

const v = (id: string, lon: number, lat: number): LiveVehicle => [lon, lat, 30, 0, id, 90, "passenger"];

describe("twin camera", () => {
  it("orbits at the reference's speed and wraps the bearing", () => {
    expect(ORBIT_DEG_PER_S).toBeCloseTo(2.7);
    expect(orbitBearing(-18, 10)).toBeCloseTo(9);
    expect(orbitBearing(179, 1)).toBeCloseTo(-178.3);
    expect(Math.round(360 / ORBIT_DEG_PER_S)).toBe(133);          // one full turn takes a little over two minutes
  });
  it("never looks straight down and stays inside what the map allows", () => {
    expect(MIN_PITCH).toBe(32);
    expect(STREET.pitch).toBeLessThanOrEqual(MAX_PITCH);
    expect(STREET.pitch).toBeGreaterThan(MIN_PITCH);
  });
  it("rides with the chosen vehicle while it is on the road, otherwise with the nearest one", () => {
    const list = [v("a", 90.40, 23.75), v("b", 90.41, 23.76)];
    expect(rideWith(list, "b", 90.40, 23.75)?.[4]).toBe("b");
    expect(rideWith(list, "gone", 90.409, 23.759)?.[4]).toBe("b");
    expect(rideWith(list, null, 90.40, 23.75)?.[4]).toBe("a");
    expect(rideWith([], "a", 0, 0)).toBeNull();
  });
  it("uses the reference's night colours", () => {
    expect(NIGHT).toMatchObject({light: "#5d7290", intensity: 0.28, backdrop: "#05070f", headlight: "#ffedb8"});
  });
});
