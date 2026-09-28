import {createBrowserRouter, Navigate} from "react-router-dom";

import {AppShell} from "./AppShell";
import {TodayPage} from "@/features/assistant/TodayPage";
import {ForecastPage} from "@/features/forecast/ForecastPage";
import {MobilityPage} from "@/features/mobility/MobilityPage";
import {ReferencesPage} from "@/features/references/ReferencesPage";
import {ResultsPage} from "@/features/results/ResultsPage";
import {SystemPage} from "@/features/system/SystemPage";
import {ControlRoomPage} from "@/features/twin/ControlRoomPage";

/** Hero photographs: Unsplash (free to use under the Unsplash License), files in public/photos, credit shown on the page. */
export const PHOTOS = {
  bus: {id: "tUXQHNpoEgg", by: "Kabiur Rahman Riyad"},
  street: {id: "OP62QfacSTk", by: "Mahibul Hasan Fahim"},
  highway: {id: "xULCIysRiBM", by: "Kabiur Rahman Riyad"},
  aerial: {id: "olFpgSOSHfE", by: "Sazzad Aryan"},
  night: {id: "NqOInJ-ttqM", by: "Marc-Olivier Jodoin"},
  lapse: {id: "56zXu3g8RJE", by: "Jan Valečka"},
} as const;

export type NavItem = {path: string; label: string; title: string; eyebrow: string; hint: string; photo: keyof typeof PHOTOS};

/** One route per page; the pages live in features/<domain>/. */
export const NAV: NavItem[] = [
  {path: "/today", label: "Today", title: "Leave on time, every day.", eyebrow: "Your assistant", hint: "Say what you need. It plans with real traffic data, asks before anything it cannot undo, and logs every decision.", photo: "bus"},
  {path: "/mobility", label: "Mobility", title: "When should you leave?", eyebrow: "Routes and departures", hint: "Traffic now, traffic at departure, the best route, and the day's congestion profile.", photo: "street"},
  {path: "/forecast", label: "Forecast", title: "See congestion before it forms.", eyebrow: "Sensor-network forecast", hint: "Every mapped road at now, +15, +30 and +60 minutes, from a validated model.", photo: "night"},
  {path: "/control-room", label: "Control Room", title: "The whole system, one screen.", eyebrow: "Digital twin", hint: "Run a fresh experiment or replay a recorded closed-loop run second by second.", photo: "lapse"},
  {path: "/results", label: "Results", title: "Does smart routing help?", eyebrow: "Evidence", hint: "The congested-corridor experiment, unseen days, confidence intervals, computed gates.", photo: "highway"},
  {path: "/references", label: "References", title: "Every source, traceable to code.", eyebrow: "Papers, data, standards, tools", hint: "Each reference names the files that use it.", photo: "aerial"},
  {path: "/system", label: "System", title: "How it fits together.", eyebrow: "Pipeline", hint: "The research question, the data flow, and the status computed from frozen evidence.", photo: "night"},
];

export const router = createBrowserRouter([
  {path: "/", element: <AppShell />, children: [
    {index: true, element: <Navigate to="/today" replace />},
    {path: "today", element: <TodayPage />},
    {path: "mobility", element: <MobilityPage />},
    {path: "forecast", element: <ForecastPage />},
    {path: "control-room", element: <ControlRoomPage />},
    {path: "results", element: <ResultsPage />},
    {path: "references", element: <ReferencesPage />},
    {path: "system", element: <SystemPage />},
    {path: "*", element: <Navigate to="/today" replace />},
  ]},
]);
