// TrafficTwin addition: the map app's small pure helpers (tested in tt.test.ts).
/** Headway's travel modes → our routing profiles. */
export const profileFor = (mode: string) => (mode === 'walk' ? 'walk' : mode === 'bicycle' ? 'bicycle' : 'car');
/** Our language name for Headway's locale ("bn" or "en"). */
export const ourLang = (locale: string) => (locale.toLowerCase().startsWith('bn') ? 'bn' : 'en');
/** A clock time for the trip sheet: Bangla digits and 24-hour time in Bangla (no "AM" in a Bangla line), 12-hour in English. */
export const clockTime = (d: Date, lang: 'bn' | 'en') =>
  lang === 'bn'
    ? d.toLocaleTimeString('bn-BD', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    : d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
/** The forecast layer's colour for a speed, as a share of the fastest speed shown (slow red → amber → green); grey without a reading. */
export const speedColour = (v: number | null | undefined, top: number) => {
  if (v == null || !(top > 0)) return '#9e9e9e';
  const r = v / top;
  return r < 0.4 ? '#d7301f' : r < 0.6 ? '#fc8d59' : r < 0.8 ? '#fdcc8a' : '#1a9850';
};
/** The forecast layer's views: Now, then the horizons the city's layer has (Dhaka: Now only). */
export const layerViews = (kind: string, horizons: number[]) => (kind === 'replay' ? ['0', ...horizons.map(String)] : ['0']);
