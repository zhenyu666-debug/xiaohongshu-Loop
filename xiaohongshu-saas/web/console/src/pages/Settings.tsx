import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import api from "@/lib/api";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import type { HealthResp } from "@/types/api";

const REFRESH_OPTIONS = [
  { label: "10 秒", value: 10_000 },
  { label: "30 秒", value: 30_000 },
  { label: "1 分钟", value: 60_000 },
  { label: "5 分钟", value: 300_000 },
];

export default function Settings() {
  const { data, isLoading } = useQuery({
    queryKey: ["health", "all"],
    queryFn: async () => (await api.get<HealthResp>("/v1/health/all")).data,
    refetchInterval: 15_000,
    retry: false,
  });

  const [refresh, setRefresh] = useLocalStorage<number>("xhs.refreshMs", 30_000);
  const [gatewayUrl, setGatewayUrl] = useLocalStorage<string>("xhs.gatewayUrl", "/api");
  const [theme, setTheme] = useLocalStorage<"light" | "dark">("xhs.theme", "light");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">设置</h2>
        <p className="text-sm text-muted-foreground">控制台偏好 · 浏览器本地存储</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>外观</CardTitle>
            <CardDescription>主题模式</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex gap-2">
              {(["light", "dark"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setTheme(t);
                    document.documentElement.classList.toggle("dark", t === "dark");
                  }}
                  className={`flex-1 rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
                    theme === t
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background hover:bg-accent"
                  }`}
                >
                  {t === "light" ? "亮色" : "暗色"}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>自动刷新</CardTitle>
            <CardDescription>看板 / 列表轮询间隔</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              {REFRESH_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  onClick={() => setRefresh(o.value)}
                  className={`rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                    refresh === o.value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background hover:bg-accent"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Gateway URL</CardTitle>
            <CardDescription>xhs-saas 后端地址（开发用）</CardDescription>
          </CardHeader>
          <CardContent>
            <input
              type="text"
              value={gatewayUrl}
              onChange={(e) => setGatewayUrl(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="/api"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              修改后需要刷新页面生效。当前由 axios 拦截器统一加前缀。
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>服务健康</CardTitle>
            <CardDescription>3 services · 每 15s 轮询</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : !data ? (
              <p className="text-sm text-muted-foreground">
                暂无 health 端点（M3 gateway 上线后启用）
              </p>
            ) : (
              <div className="space-y-1">
                {data.services.map((s: { name: string; status: "up" | "down"; latency_ms?: number }) => (
                  <div key={s.name} className="flex items-center justify-between text-sm">
                    <span>{s.name}</span>
                    <span
                      className={
                        s.status === "up"
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-destructive"
                      }
                    >
                      {s.status} {s.latency_ms ? `(${s.latency_ms}ms)` : ""}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}