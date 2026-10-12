import { expect, test } from 'vitest';
import enUS from 'src/i18n/en-US';
import bn from 'src/i18n/bn';
import enTT from 'src/i18n/en-US/tt';
import bnTT from 'src/i18n/bn/tt';
import { ourLang, profileFor } from './ttPure';

const keys = (o: Record<string, unknown>, p = ''): string[] =>
  Object.entries(o).flatMap(([k, v]) => (v && typeof v === 'object' ? keys(v as Record<string, unknown>, `${p}${k}.`) : [`${p}${k}`]));

test('every English string of the map app has a Bangla one (Headway\'s and ours)', () => {
  expect(keys(bn).sort()).toEqual(keys(enUS).sort());
  expect(keys(bnTT).sort()).toEqual(keys(enTT).sort());
});

test('placeholders survive translation', () => {
  const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
  const flat = (o: Record<string, unknown>, p = ''): [string, string][] =>
    Object.entries(o).flatMap(([k, v]) => (v && typeof v === 'object' ? flat(v as Record<string, unknown>, `${p}${k}.`) : [[`${p}${k}`, String(v)] as [string, string]]));
  const bnMap = new Map([...flat(bn), ...flat(bnTT)]);
  for (const [k, v] of [...flat(enUS), ...flat(enTT)]) expect(ph(bnMap.get(k) ?? '')).toBe(ph(v));
});

test('modes and languages map to ours', () => {
  expect([profileFor('car'), profileFor('walk'), profileFor('bicycle'), profileFor('transit')]).toEqual(['car', 'walk', 'bicycle', 'car']);
  expect([ourLang('bn'), ourLang('en-US'), ourLang('es')]).toEqual(['bn', 'en', 'en']);
});

test('service worker registration runs at once when the page has already loaded, else on load', async () => {
  const { whenLoaded } = await import('src/boot/tt');
  let ran = 0, later: (() => void) | undefined;
  const win = { addEventListener: (_: string, f: () => void) => { later = f; } } as unknown as Window;
  whenLoaded({ readyState: 'complete' }, win, () => ran++);
  expect(ran).toBe(1);
  whenLoaded({ readyState: 'loading' }, win, () => ran++);
  expect(ran).toBe(1);
  later?.();
  expect(ran).toBe(2);
});

test('forecast layer colours and views', async () => {
  const { speedColour, layerViews } = await import('./ttPure');
  expect(speedColour(null, 60)).toBe('#9e9e9e');
  expect(speedColour(10, 60)).toBe('#d7301f');
  expect(speedColour(55, 60)).toBe('#1a9850');
  expect(layerViews('replay', [15, 30, 60])).toEqual(['0', '15', '30', '60']);
  expect(layerViews('recorded_day', [15, 30, 60])).toEqual(['0']);
});

test('live simulation frames become map features', async () => {
  const { frameFeatures, ring, frameBounds } = await import('./ttSim');
  const r = ring([90.4, 23.75], 425);
  expect(r).toHaveLength(49);
  expect(r[0]?.[0]).toBeCloseTo(90.4 + 425 / (111320 * Math.cos((23.75 * Math.PI) / 180)), 6);
  const v = frameFeatures('v2x', { ambulance: [90.4, 23.75], range_m: 425, cars: [[90.401, 23.75, 1], [90.402, 23.75, 0]] });
  expect(v.map((f) => f.properties.role)).toEqual(['ring', 'car', 'car', 'ambulance']);
  expect(v[1]?.properties.color).toBe('#ff9800');
  const m = frameFeatures('mesh', { phones: [[90.4, 23.75], [90.4001, 23.75], [90.5, 23.8]], links: [[0, 1]] });
  expect(m.filter((f) => f.properties.role === 'link')).toHaveLength(1);
  expect(m.filter((f) => f.properties.color === '#e8590c' && f.properties.role === 'phone')).toHaveLength(2);
  expect(frameBounds(m)).toEqual([90.4, 23.75, 90.5, 23.8]);
  expect(frameFeatures('v2x', null)).toEqual([]);
});
