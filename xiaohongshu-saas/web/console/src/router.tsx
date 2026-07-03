import { createBrowserRouter, Navigate } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import Dashboard from "@/pages/Dashboard";
import Accounts from "@/pages/Accounts";
import Tasks from "@/pages/Tasks";
import CandidatesList from "@/pages/CandidatesList";
import CandidatesTop20 from "@/pages/CandidatesTop20";
import CandidateDetail from "@/pages/CandidateDetail";
import Settings from "@/pages/Settings";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
        {
          path: "analytics",
          element: (
            <RoadmapPage
              milestone="M4"
              title="数据分析"
              description="data-lakehouse 的 PV/UV / 转化漏斗 / Top-N 热榜"
              icon={BarChart3}
            />
          ),
        },
        { path: "settings", element: <Settings /> },
        { path: "*", element: <Navigate to="/" replace /> },
      ],
    },
  ],
  { basename: "/console" },
);

function RoadmapPage({
  milestone,
  title,
  description,
  icon: Icon,
}: {
  milestone: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <Card className="max-w-md border-dashed">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            <Icon className="h-6 w-6 text-muted-foreground" />
          </div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-sm text-muted-foreground">
            将在里程碑 <span className="font-mono font-semibold text-foreground">{milestone}</span> 上线
          </p>
        </CardContent>
      </Card>
    </div>
  );
}