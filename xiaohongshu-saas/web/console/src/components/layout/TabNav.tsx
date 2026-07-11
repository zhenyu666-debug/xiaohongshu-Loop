import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const TABS = [
  { to: "/", label: "概览", end: true },
  { to: "/accounts", label: "账号" },
  { to: "/tasks", label: "任务" },
  { to: "/analytics", label: "数据" },
  { to: "/alerts", label: "告警" },
];

export function TabNav() {
  return (
    <nav
      aria-label="概览子视图"
      className="inline-flex items-center gap-1 rounded-md border bg-card p-1 text-sm"
    >
      {TABS.map(({ to, label, end }) => (
        <NavLink
          key={to + label}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "rounded-sm px-3 py-1 font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground shadow"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
