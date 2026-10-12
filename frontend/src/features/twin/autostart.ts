/**
 * Whether the twin starts a simulation by itself when it opens. Only one simulation runs at a time on the server, so a
 * run of another city is never replaced without the person asking; and a person who pressed Stop is not overruled.
 */
const ACTIVE = ["starting", "running", "paused"];
const stopped = new Set<string>();                             // cities the person stopped during this visit to the app

export const markStopped = (city: string, on: boolean) => { if (on) stopped.add(city); else stopped.delete(city); };
export const wasStopped = (city: string) => stopped.has(city);

export type Auto = "start" | "running" | "other-city" | "wait";

/** What to do for `city` given the server's status. `status` undefined means the status has not been read yet. */
export function autostart(a: {available: boolean; city: string; status?: string; runCity?: string; stoppedByPerson: boolean}): Auto {
  if (!a.available || a.status === undefined) return "wait";
  if (ACTIVE.includes(a.status)) return a.runCity === a.city ? "running" : "other-city";
  if (a.stoppedByPerson || a.status === "failed") return "wait";         // a failed run is shown, not retried in a loop
  return "start";                                                        // idle, or a run that reached its end: start again
}
