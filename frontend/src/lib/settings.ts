/** Per-device settings kept in the browser (never sent anywhere): the low-data mode. Reads are wrapped so a blocked storage still works. */
const KEY = "tt.lowData";
export function lowData(): boolean { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } }
export function setLowData(on: boolean): void { try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* no storage: the setting lasts for this page */ } window.dispatchEvent(new Event("tt-settings")); }
