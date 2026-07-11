import { useState } from "react";
import { AlertTriangle, AlertCircle, Info, Moon, Sun, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge-extra";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/hooks/useUIStore";
import { useSSE } from "@/hooks/useSSE";
import type { AlertOut } from "@/types/api";

function getAlertIcon(level: AlertOut["level"]) {
  switch (level) {
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-yellow-400" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-red-400" />;
    default:
      return <Info className="h-4 w-4 text-blue-400" />;
  }
}

function getBadgeVariant(level: AlertOut["level"]) {
  switch (level) {
    case "warning":
      return "warning";
    case "error":
      return "destructive";
    default:
      return "secondary";
  }
}

export function AlertsCenter() {
  const { darkMode, setDarkMode } = useUIStore();
  const { events } = useSSE("/sse/stream", true);
  const [alerts, _setAlerts] = useState<AlertOut[]>([]);

  // Filter alerts by service
  const filteredAlerts = events
    .filter((e) => e.type === "alert" && typeof e.data === "object")
    .map((e) => e.data as AlertOut)
    .filter((a) => a.level);

  const allAlerts = [...alerts, ...filteredAlerts].slice(-50);

  return (
    <Card className={`${darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}`}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className={`text-base ${darkMode ? "text-slate-100" : "text-slate-900"}`}>
          告警中心
        </CardTitle>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setDarkMode(!darkMode)}
          className={darkMode ? "text-slate-300 hover:text-slate-100" : "text-slate-600 hover:text-slate-900"}
        >
          {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {allAlerts.length === 0 ? (
          <p className={`text-sm ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
            暂无告警
          </p>
        ) : (
          <div className="space-y-2">
            {allAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`flex items-start gap-3 p-2 rounded-lg ${
                  darkMode ? "bg-slate-800/50" : "bg-slate-50"
                }`}
              >
                {getAlertIcon(alert.level)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={getBadgeVariant(alert.level)}>{alert.level.toUpperCase()}</Badge>
                    <span className={`text-xs ${darkMode ? "text-slate-400" : "text-slate-500"}`}>
                      {alert.resource}
                    </span>
                  </div>
                  <p className={`text-sm mt-1 ${darkMode ? "text-slate-200" : "text-slate-700"}`}>
                    {alert.message}
                  </p>
                </div>
                <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0">
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
