import {createBrowserRouter, Navigate} from "react-router-dom";

import {AppShell} from "./AppShell";
import {LabShell} from "./LabShell";
import {PHOTOS} from "./photos";
import {TodayPage} from "@/features/assistant/TodayPage";
import {CityPage} from "@/features/forecast/CityPage";
import {ModelsPage} from "@/features/forecast/ModelsPage";
import {MobilityPage} from "@/features/mobility/MobilityPage";
import {ReferencesPage} from "@/features/references/ReferencesPage";
import {ResultsPage} from "@/features/results/ResultsPage";
import {SystemPage} from "@/features/system/SystemPage";
import {ControlRoomPage} from "@/features/twin/ControlRoomPage";

export type NavItem = {path: string; label: string; title: string; eyebrow: string; hint: string; photo: keyof typeof PHOTOS; cta: {label: string; to: string}};

/** The app: what a commuter sees. One route per page; the pages live in features/<domain>/. */
export const APP_NAV: NavItem[] = [
  {path: "/today", label: "Today", title: "Leave on time, every day.", eyebrow: "Your assistant", hint: "Say what you need. It plans with real traffic data, asks before anything it cannot undo, and tells you what it did.", photo: "bus", cta: {label: "Plan a trip →", to: "/plan"}},
  {path: "/plan", label: "Plan", title: "When should you leave?", eyebrow: "Routes and departures", hint: "Traffic now, traffic at departure, the best route, and the day's congestion profile.", photo: "street", cta: {label: "Ask the assistant →", to: "/today"}},
  {path: "/city", label: "City", title: "See congestion before it forms.", eyebrow: "The city, an hour ahead", hint: "Every measured road at now, +15, +30 and +60 minutes, from a model validated on this city's own data.", photo: "night", cta: {label: "Plan around it →", to: "/plan"}},
];

/** The lab: the research surface for the authors, the examiners and reviewers. */
export const LAB_NAV = [
  {path: "/lab/evidence", label: "Evidence", hint: "Does smart routing help? Unseen days, confidence intervals, computed gates"},
  {path: "/lab/control-room", label: "Control Room", hint: "Run a fresh digital-twin experiment or replay a recorded closed-loop run"},
  {path: "/lab/models", label: "Models", hint: "Every model on this data: compare, validate on held-out moments, train, upload"},
  {path: "/lab/references", label: "References", hint: "Every paper, dataset, standard and tool the code uses, with the files that use it"},
  {path: "/lab/system", label: "System", hint: "The pipeline and the research status computed from frozen evidence"},
];

const moved: [string, string][] = [["mobility", "/plan"], ["forecast", "/city"], ["results", "/lab/evidence"], ["control-room", "/lab/control-room"], ["references", "/lab/references"], ["system", "/lab/system"]];

export const router = createBrowserRouter([
  {path: "/", element: <AppShell />, children: [
    {index: true, element: <Navigate to="/today" replace />},
    {path: "today", element: <TodayPage />},
    {path: "plan", element: <MobilityPage />},
    {path: "city", element: <CityPage />},
    ...moved.map(([from, to]) => ({path: from, element: <Navigate to={to} replace />})),
  ]},
  {path: "/lab", element: <LabShell />, children: [
    {index: true, element: <Navigate to="/lab/evidence" replace />},
    {path: "evidence", element: <ResultsPage />},
    {path: "control-room", element: <ControlRoomPage />},
    {path: "models", element: <ModelsPage />},
    {path: "references", element: <ReferencesPage />},
    {path: "system", element: <SystemPage />},
  ]},
  {path: "*", element: <Navigate to="/today" replace />},
]);
