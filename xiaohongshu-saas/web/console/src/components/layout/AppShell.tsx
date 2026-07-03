import { Outlet } from "react-router-dom";
import { SidebarNav } from "./SidebarNav";
import { Topbar } from "./Topbar";

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-56 shrink-0 border-r bg-card md:flex md:flex-col">
        <SidebarNav />
      </aside>
      <div className="flex flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}