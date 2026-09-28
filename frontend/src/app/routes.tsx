import {createBrowserRouter, Navigate} from "react-router-dom";

import {AppShell} from "./AppShell";
import {TodayPage} from "@/features/assistant/TodayPage";
import {ForecastPage} from "@/features/forecast/ForecastPage";
import {MobilityPage} from "@/features/mobility/MobilityPage";
import {ReferencesPage} from "@/features/references/ReferencesPage";
import {ResultsPage} from "@/features/results/ResultsPage";
import {SystemPage} from "@/features/system/SystemPage";
import {ControlRoomPage} from "@/features/twin/ControlRoomPage";

/** One route per page; the pages live in features/<domain>/. */
export const NAV = [
  {path: "/today", label: "Today", hint: "Ask the assistant; it plans, asks before acting, and logs everything"},
  {path: "/mobility", label: "Mobility", hint: "Leave when? Routes now vs at departure, the day's traffic"},
  {path: "/forecast", label: "Forecast", hint: "The sensor network now and +15/+30/+60 min"},
  {path: "/control-room", label: "Control Room", hint: "Run or replay a digital-twin experiment"},
  {path: "/results", label: "Results", hint: "Does smart routing help? The evidence"},
  {path: "/references", label: "References", hint: "Every paper, dataset, standard and tool the code uses"},
  {path: "/system", label: "System", hint: "The pipeline and the computed research status"},
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
