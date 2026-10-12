/** @stadiamaps/ferrostar-webcomponents 0.57.0 ships types at dist/main.d.ts but its package.json "exports" does not point to them;
 * the four classes the app uses are declared loosely here (their real shapes are in that file). */
declare module "@stadiamaps/ferrostar-webcomponents" {
  export const FerrostarCore: any;
  export const FerrostarMap: any;
  export const BrowserLocationProvider: any;
  export const SimulatedLocationProvider: any;
}
