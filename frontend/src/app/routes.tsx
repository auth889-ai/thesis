import {createBrowserRouter, Navigate} from "react-router-dom";

import {AppShell} from "./AppShell";
import {LabShell} from "./LabShell";
import {APP_NAV, HIDDEN, LAB_NAV, type NavItem, pageFor} from "./nav";
import {ActivityPage} from "@/features/activity/ActivityPage";
import {AgentPage} from "@/features/assistant/AgentPage";
import {EmergencyPage} from "@/features/emergency/EmergencyPage";
import {OfflineAlertsPage} from "@/features/emergency/OfflineAlertsPage";
import {AddCityPage} from "@/features/forecast/AddCityPage";
import {CityPage} from "@/features/forecast/CityPage";
import {ModelsPage} from "@/features/forecast/ModelsPage";
import {ModelLabPage} from "@/features/forecast/ModelLabPage";
import {LiveTwinPage} from "@/features/livetwin/LiveTwinPage";
import {GoalsPage} from "@/features/goals/GoalsPage";
import {MobilityPage} from "@/features/mobility/MobilityPage";
import {PlanPage} from "@/features/plan/PlanPage";
import {ReferencesPage} from "@/features/references/ReferencesPage";
import {ResultsPage} from "@/features/results/ResultsPage";
import {SystemPage} from "@/features/system/SystemPage";
import {FocusHome} from "@/features/home/FocusHome";
import {HomePage} from "@/features/today/HomePage";
import {TodayPage} from "@/features/today/TodayPage";
import {CityPage3D} from "@/features/twin/CityPage3D";
import {ControlRoomPage} from "@/features/twin/ControlRoomPage";
import {SettingsPage} from "@/features/you/SettingsPage";
import {YouPage} from "@/features/you/YouPage";

export {APP_NAV, HIDDEN, LAB_NAV, pageFor, type NavItem};

const moved: [string, string][] = [["mobility", "/map"], ["forecast", "/city"], ["agent", "/messages"], ["you", "/you-lifeos"], ["results", "/lab/evidence"], ["control-room", "/lab/control-room"], ["references", "/lab/references"], ["system", "/lab/system"]];

export const router = createBrowserRouter([
  {path: "/", element: <AppShell />, children: [
    {index: true, element: <FocusHome />},
    {path: "trip", element: <HomePage />},
    {path: "3d", element: <CityPage3D />},
    {path: "add-city", element: <AddCityPage />},
    {path: "emergency", element: <EmergencyPage />},
    {path: "offline", element: <OfflineAlertsPage />},
    {path: "settings", element: <SettingsPage />},
    {path: "today", element: <TodayPage />},
    {path: "plan", element: <PlanPage />},
    {path: "goals", element: <GoalsPage />},
    {path: "goals/:id", element: <GoalsPage />},
    {path: "messages", element: <AgentPage />},
    {path: "map", element: <MobilityPage />},
    {path: "city", element: <CityPage />},
    {path: "activity", element: <ActivityPage />},
    {path: "you-lifeos", element: <YouPage />},
    ...moved.map(([from, to]) => ({path: from, element: <Navigate to={to} replace />})),
  ]},
  {path: "/lab", element: <LabShell />, children: [
    {index: true, element: <Navigate to="/lab/evidence" replace />},
    {path: "evidence", element: <ResultsPage />},
    {path: "control-room", element: <ControlRoomPage />},
    {path: "models", element: <ModelsPage />},
    {path: "model-lab", element: <ModelLabPage />},
    {path: "live-twin", element: <LiveTwinPage />},
    {path: "references", element: <ReferencesPage />},
    {path: "system", element: <SystemPage />},
  ]},
  {path: "*", element: <Navigate to="/" replace />},
], {basename: "/app"});                                                    // the map app owns "/"; these pages live under /app/
