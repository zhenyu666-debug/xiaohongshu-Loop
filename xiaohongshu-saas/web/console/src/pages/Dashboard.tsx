import { useUIStore } from "@/hooks/useUIStore";
import { TabNav } from "@/components/layout/TabNav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge-extra";
import { useLauncherStatus } from "@/hooks/useLauncherStatus";

const SERVICE_CONFIG = [
  { name: "xhs-saas", label: "小红书 SaaS", color: "#34d399" },
  { name: "pbp-api", label: "供体筛选 API", color: "#38bdf8" },
  { name: "lakehouse-api", label: "数据湖仓 API", color: "#a78bfa" },
];

export function Dashboard() {
  const { darkMode } = useUIStore();
  const { status, error } = useLauncherStatus();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">概览</h2>
        <TabNav />
      </div>

      {/* Service Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {SERVICE_CONFIG.map((svc) => {
          const svcStatus = status?.services[svc.name as keyof typeof status.services];
          const isHealthy = svcStatus?.healthy ?? false;
          const isRunning = svcStatus?.running ?? false;
          const isDisabled = svcStatus?.state === "disabled";

          return (
            <Card
              key={svc.name}
              className={`${
                darkMode ? "bg-slate-900 border-slate-800" : "bg-white"
              } ${isDisabled ? "opacity-60 border-dashed" : ""}`}
            >
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: svc.color }}
                  />
                  <CardTitle className={`text-sm ${darkMode ? "text-slate-200" : "text-slate-800"}`}>
                    {svc.label}
                  </CardTitle>
                </div>
                {isDisabled ? (
                  <Badge variant="secondary">未启用</Badge>
                ) : isHealthy ? (
                  <Badge variant="success">健康</Badge>
                ) : isRunning ? (
                  <Badge variant="warning">启动中</Badge>
                ) : (
                  <Badge variant="secondary">已停止</Badge>
                )}
              </CardHeader>
              <CardContent>
                <p className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
                  端口 {svcStatus?.port ?? svc.name.includes("xhs") ? "8080" : svc.name.includes("pbp") ? "8090" : "8091"}
                </p>
                {svcStatus?.last_error && (
                  <p className="text-xs text-red-400 mt-1">{svcStatus.last_error}</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className={darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}>
          <CardContent className="pt-4">
            <p className={`text-2xl font-bold ${darkMode ? "text-slate-100" : "text-slate-900"}`}>0</p>
            <p className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>活跃任务</p>
          </CardContent>
        </Card>
        <Card className={darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}>
          <CardContent className="pt-4">
            <p className={`text-2xl font-bold ${darkMode ? "text-slate-100" : "text-slate-900"}`}>0</p>
            <p className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>已绑定账号</p>
          </CardContent>
        </Card>
        <Card className={darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}>
          <CardContent className="pt-4">
            <p className={`text-2xl font-bold ${darkMode ? "text-slate-100" : "text-slate-900"}`}>0</p>
            <p className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>本月发布</p>
          </CardContent>
        </Card>
        <Card className={darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}>
          <CardContent className="pt-4">
            <p className={`text-2xl font-bold ${darkMode ? "text-slate-100" : "text-slate-900"}`}>0</p>
            <p className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>待处理告警</p>
          </CardContent>
        </Card>
      </div>

      {error && (
        <Card className="border-red-500/50 bg-red-500/10">
          <CardContent className="pt-4">
            <p className="text-sm text-red-400">无法连接到 Launcher: {error}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
