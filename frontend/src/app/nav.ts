import {PHOTOS} from "./photos";

export type NavItem = {path: string; key: string; icon: string; photo: keyof typeof PHOTOS; cta: string};

/** The focused Home shows three things; every other page is behind "More" (owner, 2026-10-08). */
export const MORE = (): NavItem[] => APP_NAV.filter((n) => n.path !== "/");

/**
 * The traffic app, in the order of the menu (owner, 2026-10-06). Each page's words are in the translation files
 * under `nav.<key>.*`. The photographs are streets of the world, not one city. The LIFE OS pages are kept in the
 * router below and reached by their address only; they are not in this menu.
 */
export const APP_NAV: NavItem[] = [
  {path: "/", key: "home", icon: "⌂", photo: "tokyo", cta: "/3d"},
  {path: "/trip", key: "trip", icon: "↗", photo: "tokyo", cta: "/3d"},                 // the former Home, unchanged (owner, 2026-10-08)
  {path: "/3d", key: "city3d", icon: "▦", photo: "shibuya", cta: "/emergency"},
  {path: "/add-city", key: "addCity", icon: "＋", photo: "nairobi", cta: "/"},
  {path: "/emergency", key: "emergency", icon: "✚", photo: "night", cta: "/3d"},
  {path: "/offline", key: "offline", icon: "⇄", photo: "tokyoHighway", cta: "/emergency"},
  {path: "/lab", key: "research", icon: "⚗", photo: "interchange", cta: "/lab/evidence"},
  {path: "/settings", key: "settings", icon: "⚙", photo: "lagos", cta: "/"},
];
/** The LIFE OS pages: addresses only, so their hero band still has words. */
export const HIDDEN: NavItem[] = [
  {path: "/today", key: "today", icon: "⌂", photo: "tokyo", cta: "/map"},
  {path: "/city", key: "city", icon: "▦", photo: "shibuya", cta: "/lab/models"},
  {path: "/map", key: "map", icon: "◈", photo: "interchange", cta: "/city"},
  {path: "/plan", key: "plan", icon: "▤", photo: "newyork", cta: "/messages"},
  {path: "/goals", key: "goals", icon: "◎", photo: "jakarta", cta: "/messages"},
  {path: "/messages", key: "messages", icon: "✉", photo: "nairobi", cta: "/goals"},
  {path: "/activity", key: "activity", icon: "≡", photo: "tokyoHighway", cta: "/settings"},
  {path: "/you-lifeos", key: "you", icon: "⚙", photo: "lagos", cta: "/today"},
];

/** The page whose words the hero band shows: an exact match for the home, a prefix match for every other address. */
export const pageFor = (pathname: string): NavItem =>
  [...APP_NAV, ...HIDDEN].find((n) => (n.path === "/" ? pathname === "/" : pathname.startsWith(n.path))) ?? APP_NAV[0];

/** The lab: the research surface for the authors, the examiners and reviewers. */
export const LAB_NAV = [
  {path: "/lab/evidence", label: "Evidence", hint: "Does smart routing help? Unseen days, confidence intervals, computed gates"},
  {path: "/lab/control-room", label: "Control Room", hint: "Run a fresh digital-twin experiment or replay a recorded closed-loop run"},
  {path: "/lab/models", label: "Models", hint: "Every model on this data: compare, validate on held-out moments, train, upload"},
  {path: "/lab/model-lab", label: "Model Lab", hint: "Pick a sensor, a moment and a model; the forecast is computed now by the thesis code"},
  {path: "/lab/live-twin", label: "Live twin", hint: "A running simulation of the corridor: place a crash or an ambulance and watch three forecasters learn"},
  {path: "/lab/references", label: "References", hint: "Every paper, dataset, standard and tool the code uses, with the files that use it"},
  {path: "/lab/system", label: "System", hint: "The pipeline and the research status computed from frozen evidence"},
];
