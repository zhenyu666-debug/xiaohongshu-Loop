import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import Dashboard from "@/pages/Dashboard";
import Accounts from "@/pages/Accounts";
import Tasks from "@/pages/Tasks";
import AnalyticsOverview from "@/pages/AnalyticsOverview";
import AlertsCenter from "@/pages/AlertsCenter";
import Settings from "@/pages/Settings";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("pages render", () => {
  it("Dashboard", () => {
    render(wrap(<Dashboard />));
    // "概览" appears in both the page <h2> and the TabNav link, so just confirm at least one match exists.
    expect(screen.getAllByText(/概览/).length).toBeGreaterThan(0);
  });
  it("Accounts", () => {
    render(wrap(<Accounts />));
    expect(screen.getByText(/账号管理/)).toBeInTheDocument();
  });
  it("Tasks", () => {
    render(wrap(<Tasks />));
    expect(screen.getByText(/定时任务/)).toBeInTheDocument();
  });
  it("AnalyticsOverview", () => {
    render(wrap(<AnalyticsOverview />));
    expect(screen.getByText(/今日概览/)).toBeInTheDocument();
  });
  it("AlertsCenter", () => {
    render(wrap(<AlertsCenter />));
    expect(screen.getByText(/告警中心/)).toBeInTheDocument();
  });
  it("Settings", () => {
    render(wrap(<Settings />));
    expect(screen.getByText(/设置/)).toBeInTheDocument();
  });
});