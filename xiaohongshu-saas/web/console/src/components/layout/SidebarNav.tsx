import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  ListTodo,
  FlaskConical,
  BarChart3,
  Settings as SettingsIcon,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "概览", icon: LayoutDashboard, end: true },
  { to: "/accounts", label: "账号", icon: Users },
  { to: "/tasks", label: "任务", icon: ListTodo },
  { to: "/candidates", label: "候选", icon: FlaskConical },
  { to: "/analytics", label: "数据", icon: BarChart3 },
  { to: "/settings", label: "设置", icon: SettingsIcon },
];

export function SidebarNav() {
  return (
    <nav className="flex flex-col gap-1 px-3 py-4">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )
          }
        >
          <Icon className="h-4 w-4" />
          <span>{label}</span>
        </NavLink>
      ))}
      <div className="mt-auto flex items-center gap-2 px-3 pt-6 text-xs text-muted-foreground">
        <Activity className="h-3 w-3" />
        <span>v1.1.0</span>
      </div>
    </nav>
  );
}