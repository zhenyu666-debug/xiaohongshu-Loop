import { TabNav } from "@/components/layout/TabNav";
import { useUIStore } from "@/hooks/useUIStore";
import { AlertsCenter } from "@/components/AlertsCenter";

export function AlertsPage() {
  const { darkMode: _darkMode } = useUIStore();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">告警中心</h2>
        <TabNav />
      </div>
      <AlertsCenter />
    </div>
  );
}
