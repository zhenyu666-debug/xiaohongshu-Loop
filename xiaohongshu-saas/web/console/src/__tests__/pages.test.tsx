import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import Dashboard from "@/pages/Dashboard";
import Accounts from "@/pages/Accounts";
import Tasks from "@/pages/Tasks";
import Settings from "@/pages/Settings";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("pages render skeleton / heading", () => {
  it("Dashboard", () => {
    render(wrap(<Dashboard />));
    expect(screen.getByText(/概览/)).toBeInTheDocument();
  });
  it("Accounts", () => {
    render(wrap(<Accounts />));
    expect(screen.getByText(/账号管理/)).toBeInTheDocument();
  });
  it("Tasks", () => {
    render(wrap(<Tasks />));
    expect(screen.getByText(/定时任务/)).toBeInTheDocument();
  });
  it("Settings", () => {
    render(wrap(<Settings />));
    expect(screen.getByText(/设置/)).toBeInTheDocument();
  });
});