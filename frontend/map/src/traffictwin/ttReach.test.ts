import { describe, expect, it } from 'vitest';
import { reachBounds, reachColor, reachFeatures, reachSummary, type LiveHospital } from './ttReach';

const h = (name: string, to: number | null): LiveHospital => ({ osm_id: name, name, lat: 23.7, lon: 90.4, time_s: 100, distance_m: 900, to_point_s: to, reached_within_min: to == null ? null : to <= 600 ? 10 : to <= 1200 ? 20 : to <= 1800 ? 30 : null,
  contours: [10, 20, 30].map((m) => ({ minutes: m, geometry: { type: 'Polygon', coordinates: [[[90.4, 23.7], [90.41, 23.7], [90.4, 23.71], [90.4, 23.7]]] } })) });

describe('live reach', () => {
  it('draws the largest contours first and colours by minutes', () => {
    const f = reachFeatures([h('A', 300), h('B', null)]);
    expect(f.map((x) => x.properties?.minutes)).toEqual([30, 30, 20, 20, 10, 10]);
    expect(f[4]?.properties?.color).toBe(reachColor(10));
  });
  it('bounds cover every ring', () => {
    expect(reachBounds(reachFeatures([h('A', 1)]))).toEqual([90.4, 23.7, 90.41, 23.71]);
    expect(reachBounds([])).toBeNull();
  });
  it('summarises the nearest hospital in the ambulance direction', () => {
    expect(reachSummary({ available: true, hospitals: [h('A', 1300)] })).toEqual({ name: 'A', minutes: 22, within: 30 });
    expect(reachSummary({ available: true, hospitals: [h('A', null)] })?.minutes).toBeNull();
    expect(reachSummary({ available: false })).toBeNull();
  });
});
