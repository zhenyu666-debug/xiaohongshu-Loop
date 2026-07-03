import { Moon, Sun, Search } from "lucide-react";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { HealthBadge } from "./HealthBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Topbar() {
  const [theme, setTheme] = useLocalStorage<"light" | "dark">("xhs.theme", "light");

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <header className="flex h-14 items-center justify-between border-b bg-card px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">Unified Console</h1>
        <span className="text-xs text-muted-foreground">xhs-saas · pbp · lakehouse</span>
      </div>
      <div className="flex flex-1 items-center justify-center px-6">
        <div className="relative w-full max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="搜索账号 / 任务 / 候选... (Phase 2)" className="pl-9" disabled />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <HealthBadge />
        <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}