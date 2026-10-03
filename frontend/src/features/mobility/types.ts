/** Shapes returned by /api/commute/plan and /api/analyze (backend/app/commute, backend/app/routing/trip_analysis). */
export type Place = {label?: string; lat: number; lng: number};

export type CommuteOption = {route: string; covered: boolean; expected_s: number; on_time_probability: number | null; worst_corridor: string | null};
export type Coverage = {city_id: string; watched: boolean; steps_own: number; corridors_touched: string[]; covered: boolean; samples: number; first_utc: string | null; last_utc: string | null; action: string | null};
export type CommutePlan = {coverage?: Coverage; 
  city: string; arrive_by_local: string; now_utc: string; buffer_min: number; on_time_target: number; origin: Place; destination: Place;
  recommended: {depart_utc: string; depart_local: string; route: string; on_time_probability: number | null; expected_s: number; leave_in_min: number};
  routes: {key: string; description?: string; distance_m: number | null; static_s: number | null; corridors: string[]; now: CommuteOption; at_departure: CommuteOption}[];
  departures: {depart_local: string; best_route: string; on_time_probability: number | null; expected_s: number}[];
  day_profile: {slot: number; time: string; expected_s: number | null; expected_level: number | null}[];
  congestion_window: {from: string; to: string; peak_level: number} | null;
  provenance: {kind: string; traffic: string; routing: string; probability: string};
};

export type Segment = {speed?: string; colour?: string; coordinates: [number, number][]};
export type Route = {key: string; index: number; eta_now_s: number; distance_m: number | null; category_now: string; recommended: boolean; status?: string; segments: Segment[]; forecast: Record<string, {eta_s: number; risk: string; covered: boolean}>};
export type TripResult = {
  run_id?: string; city: string; horizon_min: number; origin: Place; destination: Place; retrieved_at?: string; forecastable?: boolean; result_source?: string;
  current: {eta_s: number; route: string; congestion: string; distance_m: number | null};
  forecast: {eta_s: number; risk: string; covered: boolean; model: string | null};
  decision: {recommended: string; saving_s: number; reason: string; basis?: string};
  routes: Route[];
  source: {traffic: string; traffic_basis?: string; is_live: boolean; traffic_coverage?: boolean; routing: string | null; incidents?: {type?: string; severity?: string; description?: string}[]};
  forecast_decision?: {model?: string; label?: string; status?: string; why?: string};
  routing_policy?: {policy?: string};
  provenance?: Record<string, string>;
};
export type TripJob = {job: string; status: string; stage?: string; error?: string; result?: TripResult};

export const CAT_COLOUR: Record<string, string> = {NORMAL: "#177b58", SLOW: "#a86b00", TRAFFIC_JAM: "#c2413a", UNKNOWN: "#9aa8a5", UNAVAILABLE: "#9aa8a5"};
export const ROUTE_COLOUR = {recommended: "#4a5d23", fastestNow: "#3d6b8a", other: "#9aa8a5"};

/** "HH:MM" today, or tomorrow when already past, as an ISO instant. */
export function nextLocalTime(hhmm: string, now = new Date()): string {
  const [h, m] = hhmm.split(":").map(Number);
  const d = new Date(now); d.setHours(h, m, 0, 0);
  if (d.getTime() < now.getTime()) d.setDate(d.getDate() + 1);
  return d.toISOString();
}

export const levelColour = (l: number | null | undefined) => (l == null ? "#9aa8a5" : l >= 2 ? "#c2413a" : l >= 1 ? "#a86b00" : "#177b58");
