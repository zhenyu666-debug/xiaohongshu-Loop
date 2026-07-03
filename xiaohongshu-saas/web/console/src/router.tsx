import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import Dashboard from "@/pages/Dashboard";
import Accounts from "@/pages/Accounts";
import Tasks from "@/pages/Tasks";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <AppShell />,
      children: [
        { index: true, element: <Dashboard /> },
        { path: "accounts", element: <Accounts /> },
        { path: "tasks", element: <Tasks /> },
        { path: "candidates", element: <PlaceholderPage title="候选" subtitle="M3 milestone" /> },
        { path: "analytics", element: <PlaceholderPage title="数据分析" subtitle="M4 milestone" /> },
        { path: "settings", element: <PlaceholderPage title="设置" subtitle="M2 milestone" /> },
        { path: "*", element: <Navigate to="/" replace /> },
      ],
    },
  ],
  { basename: "/console" },
);

function PlaceholderPage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
      </div>
    </div>
  );
}