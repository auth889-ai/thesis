/**
 * Vehicle shapes for the 3D twin.
 *
 * The box sizes and colour palettes of the four archetypes (car, auto-rickshaw, bus, two-wheeler) are taken from
 * karthiksenv/real-time-digital-traffic-simulation (MIT licence), src/scene/Vehicles.jsx at commit f8ef3592, where
 * they are three.js boxes; here they are plain numbers that become extruded polygons on the map. Recorded in
 * third_party/SOURCES.md. Everything else in this file is ours, including the EXTRA colours: everyday paint colours
 * added so that neighbouring vehicles differ more. A vehicle's colour is decoration. It is chosen from its id and
 * carries no data, and the map's legend says so. Two colours are the exception, in a simulated ambulance run only:
 * the ambulance itself (AMBULANCE_COLOUR) and a vehicle that is making way after receiving its alert (WAY_COLOUR).
 */
export type Archetype = "car" | "auto" | "bus" | "bike" | "ambulance";
export const AMBULANCE_COLOUR = "#d21f1f", WAY_COLOUR = "#f5a623";
/** One box in metres: width, height, length, height of its centre above the road, offset of its centre along the heading. */
export type Box = {w: number; h: number; d: number; y: number; z: number};
/** A vehicle as the live run publishes it: lon, lat, km/h, equipped, id, heading in degrees clockwise from north, SUMO vehicle class. */
export type LiveVehicle = [number, number, number, number, string, number, string];

export const SHAPES: Record<Archetype, Box[]> = {
  car: [{w: 1.75, h: 0.95, d: 4.2, y: 0.75, z: 0}, {w: 1.6, h: 0.7, d: 2.1, y: 1.55, z: -0.25}],
  auto: [{w: 1.35, h: 1.15, d: 2.7, y: 0.85, z: 0}, {w: 1.45, h: 0.1, d: 2.85, y: 1.62, z: 0}, {w: 0.9, h: 0.5, d: 0.5, y: 0.65, z: 1.45}],
  bus: [{w: 2.45, h: 2.7, d: 10.5, y: 1.75, z: 0}, {w: 2.3, h: 0.25, d: 10.2, y: 3.2, z: 0}],
  bike: [{w: 0.5, h: 0.75, d: 2.0, y: 0.7, z: 0}, {w: 0.55, h: 0.9, d: 0.55, y: 1.5, z: -0.2}],
  ambulance: [{w: 2.2, h: 2.2, d: 6.5, y: 1.4, z: 0}, {w: 1.2, h: 0.25, d: 0.5, y: 2.65, z: 1.5}],      // ours: a box van with a light bar, at SUMO's emergency-class length
};
export const PALETTES: Record<Archetype, string[]> = {
  car: ["#e8e8e8", "#d5d8dc", "#b8bcc2", "#f5f5f2", "#8f959c", "#2f3338", "#7a1f1f", "#1d3a5f", "#c8c2b4"],
  auto: ["#f2c81e", "#e9c528", "#f5cf2a"],
  bus: ["#e2711d", "#d95f18", "#3f7d3a", "#c23b22"],
  bike: ["#22262b", "#3a3f45", "#5c1f1f", "#1f3a5c", "#666c73"],
  ambulance: [],
};
/** Ours, not the reference's. */
export const EXTRA: Record<Archetype, string[]> = {
  car: ["#ffffff", "#c0c4c9", "#6b7076", "#0f1113", "#2456a6", "#b3261e", "#1f5c3a", "#8a6d3b"],
  auto: [],
  bus: ["#f4f4f1", "#2456a6"],
  bike: ["#b3261e", "#e6e6e3", "#9aa0a6"],
  ambulance: [AMBULANCE_COLOUR],
};
export const colours = (kind: Archetype) => [...PALETTES[kind], ...EXTRA[kind]];

/** Which shape a vehicle class is drawn with: a SUMO class, or a class name from a city's vehicle mix (Bus_Minibus, Motor_Cycle, CNG ...). Only four everyday shapes exist, so a cycle rickshaw shares the auto-rickshaw's and a pickup the bus's. SUMO's own class "emergency" is the ambulance of an ambulance run. */
export function archetype(vclass: string): Archetype {
  const c = vclass.toLowerCase();
  if (c === "emergency") return "ambulance";
  if (c.includes("rickshaw") || c.includes("cng") || c === "taxi") return "auto";
  if (c.includes("bus") || c === "coach" || c.includes("truck") || c === "trailer" || c === "delivery" || c === "special_purpose") return "bus";
  if (c.replace("_", "") === "motorcycle" || c === "moped" || c === "bicycle") return "bike";
  return "car";
}

const hash = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h; };
const M_PER_DEG = 111_320;

/** The extruded polygons of one vehicle: each box becomes a rectangle turned to the heading, with a base and a top height. `markWay`: in an ambulance run, a vehicle whose flag is set is making way and gets WAY_COLOUR. */
export function vehicleFeatures(v: LiveVehicle, markWay = false) {
  const [lon, lat, kmh, flag, id, angle, vclass] = v;
  const kind = archetype(vclass);
  const a = (angle * Math.PI) / 180, fx = Math.sin(a), fy = Math.cos(a), rx = Math.cos(a), ry = -Math.sin(a);
  const dLat = 1 / M_PER_DEG, dLon = 1 / (M_PER_DEG * Math.cos((lat * Math.PI) / 180));
  const paints = colours(kind), colour = markWay && flag === 1 && kind !== "ambulance" ? WAY_COLOUR : paints[hash(id) % paints.length];
  const length = SHAPES[kind][0].d;
  return SHAPES[kind].map((b) => {
    const cz = b.z - length / 2;                       // SUMO reports the front bumper; the shape is centred half a length behind it
    const corner = (sf: number, sr: number): [number, number] => {
      const f = cz + (sf * b.d) / 2, r = (sr * b.w) / 2;
      return [lon + (fx * f + rx * r) * dLon, lat + (fy * f + ry * r) * dLat];
    };
    const ring = [corner(1, 1), corner(1, -1), corner(-1, -1), corner(-1, 1), corner(1, 1)];
    return {type: "Feature" as const, geometry: {type: "Polygon" as const, coordinates: [ring]},
            properties: {id, colour, base: +(b.y - b.h / 2).toFixed(2), height: +(b.y + b.h / 2).toFixed(2), kmh, vclass, kind}};
  });
}

/** Positions part-way between two snapshots, so vehicles glide between one-second readings instead of jumping. */
export function between(prev: LiveVehicle[], next: LiveVehicle[], share: number): LiveVehicle[] {
  if (share >= 1 || !prev.length) return next;
  const was = new Map(prev.map((p) => [p[4], p]));
  return next.map((n) => {
    const p = was.get(n[4]);
    return p ? [p[0] + (n[0] - p[0]) * share, p[1] + (n[1] - p[1]) * share, n[2], n[3], n[4], n[5], n[6]] as LiveVehicle : n;
  });
}

/** The colour of one signal head from SUMO's phase string (one letter per controlled link). */
export function signalColour(state: string | undefined, link: number): string {
  const c = state?.[link];
  return c === "G" || c === "g" ? "#2e9e4f" : c === "y" || c === "Y" ? "#e0a81c" : c === "r" || c === "R" ? "#c8322b" : "#8a8f96";
}
