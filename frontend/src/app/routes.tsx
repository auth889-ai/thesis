import {createBrowserRouter, Navigate} from "react-router-dom";

import {AppShell} from "./AppShell";
import {LabShell} from "./LabShell";
import {PHOTOS} from "./photos";
import {ActivityPage} from "@/features/activity/ActivityPage";
import {AgentPage} from "@/features/assistant/AgentPage";
import {GoalsPage} from "@/features/goals/GoalsPage";
import {TodayPage} from "@/features/today/TodayPage";
import {YouPage} from "@/features/you/YouPage";
import {CityPage} from "@/features/forecast/CityPage";
import {ModelsPage} from "@/features/forecast/ModelsPage";
import {MobilityPage} from "@/features/mobility/MobilityPage";
import {ReferencesPage} from "@/features/references/ReferencesPage";
import {ResultsPage} from "@/features/results/ResultsPage";
import {SystemPage} from "@/features/system/SystemPage";
import {ControlRoomPage} from "@/features/twin/ControlRoomPage";

export type NavItem = {path: string; label: string; title: string; eyebrow: string; hint: string; photo: keyof typeof PHOTOS; cta: {label: string; to: string}; nav?: boolean};

/** The app: one personal operating system. The five pages are the navigation; Plan and City are reached from Today and the Agent. */
export const APP_NAV: NavItem[] = [
  {path: "/today", label: "Today", title: "Your day, already thought through.", eyebrow: "LIFE OS", hint: "What is on, when to leave, what is at risk, and what the assistant suggests, computed now from your calendar, tasks and the roads.", photo: "bus", cta: {label: "Ask the agent →", to: "/agent"}, nav: true},
  {path: "/agent", label: "Agent", title: "Say what you need.", eyebrow: "Your assistant", hint: "It reads your goal, proposes its steps, and waits for you; it asks before anything it cannot undo, and every step is logged.", photo: "street", cta: {label: "See your goals →", to: "/goals"}, nav: true},
  {path: "/goals", label: "Goals", title: "Everything you asked for.", eyebrow: "Goals", hint: "Progress, the next action, what is at risk, and what each goal created.", photo: "crossing", cta: {label: "New goal →", to: "/agent"}, nav: true},
  {path: "/activity", label: "Activity", title: "What happened, in plain words.", eyebrow: "Activity", hint: "Every action, approval, refusal and replan, from a log the server can verify.", photo: "lapse", cta: {label: "Your permissions →", to: "/you"}, nav: true},
  {path: "/you", label: "You", title: "What it knows, and what you allow.", eyebrow: "You", hint: "Memory, preferences, places, linked calendars, standing permissions, and the export or erasure of everything.", photo: "rest", cta: {label: "Back to today →", to: "/today"}, nav: true},
  {path: "/plan", label: "Plan", title: "When should you leave?", eyebrow: "Routes and departures", hint: "Traffic now, traffic at departure, the best route, and the day's congestion profile.", photo: "rickshaws", cta: {label: "Ask the agent →", to: "/agent"}},
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
    {path: "agent", element: <AgentPage />},
    {path: "goals", element: <GoalsPage />},
    {path: "goals/:id", element: <GoalsPage />},
    {path: "activity", element: <ActivityPage />},
    {path: "you", element: <YouPage />},
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
