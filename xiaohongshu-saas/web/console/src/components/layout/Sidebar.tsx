import { Search, User, Settings, Home } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/hooks/useUIStore";

const navItems = [
  { to: "/", icon: Home, label: "首页" },
  { to: "/accounts", icon: User, label: "账号" },
  { to: "/settings", icon: Settings, label: "设置" },
];

export function Sidebar() {
  const location = useLocation();
  const { darkMode } = useUIStore();

  return (
    <aside
      className={`w-56 border-r shrink-0 ${
        darkMode ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"
      }`}
    >
      <div className="p-4">
        <div className="relative">
          <Search className={cn("absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4", darkMode ? "text-slate-500" : "text-slate-400")} />
          <input
            type="text"
            placeholder="搜索..."
            className={cn(
              "w-full pl-9 pr-3 py-2 rounded-lg text-sm",
              darkMode
                ? "bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500"
                : "bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400"
            )}
          />
        </div>
      </div>
      <nav className="px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.to;
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? darkMode
                    ? "bg-slate-800 text-white"
                    : "bg-slate-100 text-slate-900"
                  : darkMode
                  ? "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
