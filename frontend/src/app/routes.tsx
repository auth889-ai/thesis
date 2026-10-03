import {createBrowserRouter, Navigate} from "react-router-dom";

import {AppShell} from "./AppShell";
import {LabShell} from "./LabShell";
import {PHOTOS} from "./photos";
import {ActivityPage} from "@/features/activity/ActivityPage";
import {AgentPage} from "@/features/assistant/AgentPage";
import {CityPage} from "@/features/forecast/CityPage";
import {ModelsPage} from "@/features/forecast/ModelsPage";
import {GoalsPage} from "@/features/goals/GoalsPage";
import {MobilityPage} from "@/features/mobility/MobilityPage";
import {PlanPage} from "@/features/plan/PlanPage";
import {ReferencesPage} from "@/features/references/ReferencesPage";
import {ResultsPage} from "@/features/results/ResultsPage";
import {SystemPage} from "@/features/system/SystemPage";
import {TodayPage} from "@/features/today/TodayPage";
import {ControlRoomPage} from "@/features/twin/ControlRoomPage";
import {YouPage} from "@/features/you/YouPage";

export type NavItem = {path: string; label: string; icon: string; title: string; eyebrow: string; hint: string; photo: keyof typeof PHOTOS; cta: {label: string; to: string}};

/** The app, in the order of the sidebar. The photographs are streets of the world, not one city. */
export const APP_NAV: NavItem[] = [
  {path: "/city", label: "City", icon: "▦", title: "Who sees the jam first?", eyebrow: "Road traffic, forecast and checked", hint: "Every measured road now and 15, 30, 60 minutes ahead from models reproduced from their papers; which roads are about to tip; when to leave to arrive on time at 90 %.", photo: "shibuya", cta: {label: "How good is each model? →", to: "/lab/models"}},
  {path: "/map", label: "Map", icon: "◈", title: "When should you leave?", eyebrow: "Plan your route", hint: "Traffic now, traffic at departure, the best route, the rail option, and the latest reliable time to leave.", photo: "interchange", cta: {label: "See the city →", to: "/city"}},
  {path: "/today", label: "Today", icon: "⌂", title: "Make my day actually work.", eyebrow: "LIFE OS", hint: "Your calendar, tasks and the roads, checked together: what is on, when to leave, what is at risk, and what to do about it.", photo: "tokyo", cta: {label: "Plan a trip →", to: "/map"}},
  {path: "/plan", label: "Plan", icon: "▤", title: "A smoother day, your way.", eyebrow: "Your day, optimised", hint: "The day as one timeline with the travel between its commitments, the best times to leave, and the changes that keep it on track.", photo: "newyork", cta: {label: "Ask the assistant →", to: "/messages"}},
  {path: "/goals", label: "Goals", icon: "◎", title: "Turn what matters into a plan you can follow.", eyebrow: "Your goals", hint: "Progress, the next action, what is at risk, and what each goal created.", photo: "jakarta", cta: {label: "New goal →", to: "/messages"}},
  {path: "/messages", label: "Messages", icon: "✉", title: "Say what you need.", eyebrow: "Your assistant", hint: "It reads your goal, proposes its steps, waits for you, asks before anything it cannot undo, and logs every step.", photo: "nairobi", cta: {label: "See your goals →", to: "/goals"}},
  {path: "/settings", label: "Settings", icon: "⚙", title: "Your profile, your city.", eyebrow: "Settings", hint: "Who you are and where you live, what the assistant remembers, what it may do, linked calendars, and the export or erasure of everything.", photo: "lagos", cta: {label: "Back to today →", to: "/today"}},
];
export const SECONDARY: NavItem[] = [
  {path: "/activity", label: "Activity", icon: "≡", title: "What happened, in plain words.", eyebrow: "Activity", hint: "Every action, approval, refusal and replan, from a log the server can verify.", photo: "tokyoHighway", cta: {label: "Your permissions →", to: "/settings"}},
];

/** The lab: the research surface for the authors, the examiners and reviewers. */
export const LAB_NAV = [
  {path: "/lab/evidence", label: "Evidence", hint: "Does smart routing help? Unseen days, confidence intervals, computed gates"},
  {path: "/lab/control-room", label: "Control Room", hint: "Run a fresh digital-twin experiment or replay a recorded closed-loop run"},
  {path: "/lab/models", label: "Models", hint: "Every model on this data: compare, validate on held-out moments, train, upload"},
  {path: "/lab/references", label: "References", hint: "Every paper, dataset, standard and tool the code uses, with the files that use it"},
  {path: "/lab/system", label: "System", hint: "The pipeline and the research status computed from frozen evidence"},
];

const moved: [string, string][] = [["mobility", "/map"], ["forecast", "/city"], ["agent", "/messages"], ["you", "/settings"], ["results", "/lab/evidence"], ["control-room", "/lab/control-room"], ["references", "/lab/references"], ["system", "/lab/system"]];

export const router = createBrowserRouter([
  {path: "/", element: <AppShell />, children: [
    {index: true, element: <Navigate to="/city" replace />},
    {path: "today", element: <TodayPage />},
    {path: "plan", element: <PlanPage />},
    {path: "goals", element: <GoalsPage />},
    {path: "goals/:id", element: <GoalsPage />},
    {path: "messages", element: <AgentPage />},
    {path: "map", element: <MobilityPage />},
    {path: "city", element: <CityPage />},
    {path: "activity", element: <ActivityPage />},
    {path: "settings", element: <YouPage />},
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
  {path: "*", element: <Navigate to="/city" replace />},
]);
