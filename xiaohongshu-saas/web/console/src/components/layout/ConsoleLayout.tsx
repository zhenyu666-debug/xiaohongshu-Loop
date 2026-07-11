import { Outlet } from "react-router-dom";
import { useUIStore } from "@/hooks/useUIStore";
import { DarkModeToggle } from "@/components/DarkModeToggle";

export function ConsoleLayout() {
  const { darkMode } = useUIStore();

  return (
    <div className={`min-h-screen ${darkMode ? "bg-slate-950 text-slate-100" : "bg-slate-50 text-slate-900"}`}>
      <header
        className={`border-b ${
          darkMode ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"
        }`}
      >
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold">小红书 SaaS 控制台</h1>
          <div className="flex items-center gap-4">
            <span className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>v1.1.0</span>
            <DarkModeToggle />
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
