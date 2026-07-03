import { useState } from "react";
import Dashboard from "./pages/Dashboard";
import Accounts from "./pages/Accounts";
import Tasks from "./pages/Tasks";

type Tab = "dashboard" | "accounts" | "tasks";

const NAV: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "概览" },
  { id: "accounts", label: "账号" },
  { id: "tasks", label: "任务" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5" }}>
      <header
        style={{
          background: "#1a1a1a",
          color: "#fff",
          padding: "0 24px",
          lineHeight: "56px",
          display: "flex",
          alignItems: "center",
          gap: "32px",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 18 }}>xhs-saas</span>
        <nav style={{ display: "flex", gap: "4px" }}>
          {NAV.map((n) => (
            <button
              key={n.id}
              onClick={() => setTab(n.id)}
              style={{
                background: tab === n.id ? "#333" : "transparent",
                color: tab === n.id ? "#fff" : "#aaa",
                border: "none",
                cursor: "pointer",
                padding: "8px 16px",
                borderRadius: 6,
                fontSize: 14,
              }}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </header>

      <main style={{ padding: "24px" }}>
        {tab === "dashboard" && <Dashboard />}
        {tab === "accounts" && <Accounts />}
        {tab === "tasks" && <Tasks />}
      </main>
    </div>
  );
}
