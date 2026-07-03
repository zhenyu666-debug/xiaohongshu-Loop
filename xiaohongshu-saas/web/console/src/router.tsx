import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import Dashboard from "@/pages/Dashboard";
import Accounts from "@/pages/Accounts";
import Tasks from "@/pages/Tasks";
import CandidatesList from "@/pages/CandidatesList";
import CandidatesTop20 from "@/pages/CandidatesTop20";
import CandidateDetail from "@/pages/CandidateDetail";
import AnalyticsOverview from "@/pages/AnalyticsOverview";
import AnalyticsPvUv from "@/pages/AnalyticsPvUv";
import AnalyticsFunnel from "@/pages/AnalyticsFunnel";
import AnalyticsTopItems from "@/pages/AnalyticsTopItems";
import Settings from "@/pages/Settings";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <AppShell />,
      children: [
        { index: true, element: <Dashboard /> },
        { path: "accounts", element: <Accounts /> },
        { path: "tasks", element: <Tasks /> },
        { path: "candidates", element: <CandidatesList /> },
        { path: "candidates/top20", element: <CandidatesTop20 /> },
        { path: "candidates/:id", element: <CandidateDetail /> },
        { path: "analytics", element: <AnalyticsOverview /> },
        { path: "analytics/pv-uv", element: <AnalyticsPvUv /> },
        { path: "analytics/funnel", element: <AnalyticsFunnel /> },
        { path: "analytics/top-items", element: <AnalyticsTopItems /> },
        { path: "settings", element: <Settings /> },
        { path: "*", element: <Navigate to="/" replace /> },
      ],
    },
  ],
  { basename: "/console" },
);