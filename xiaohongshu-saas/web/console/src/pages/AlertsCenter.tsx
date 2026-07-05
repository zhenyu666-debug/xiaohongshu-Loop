import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Radio, AlertTriangle, AlertCircle, Info, RotateCcw } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import api from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { cn } from "@/lib/utils";

interface RecentItem {
  topic: string;
  task_id?: number;
  ok?: boolean;
  ts?: number;
  [k: string]: unknown;
}

interface AlertsResp {
  rules: { id: string; event: string; threshold: number; severity: string }[];
  event_counters: Record<string, number>;
  window_seconds: number;
}

const SEV_ICON = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

export default function AlertsCenter() {
  const qc = useQueryClient();
  const events = useQuery({
    queryKey: ["alerts", "events"],
    queryFn: async () => (await api.get<{ items: RecentItem[]; total: number }>("/v1/events/recent?limit=50")).data,
    refetchInterval: 30_000,
  });
  const rules = useQuery({
    queryKey: ["alerts", "rules"],
    queryFn: async () => (await api.get<AlertsResp>("/v1/alerts/recent")).data,
    refetchInterval: 60_000,
  });

  const live = useSSE<RecentItem>("/api/v1/events/stream?topic=all", {
    onEvent: () => {
      // Invalidate periodic snapshots so the panel refreshes with live items.
      qc.invalidateQueries({ queryKey: ["alerts", "events"] });
    },
  });

  useEffect(() => {
    // Visible feedback on connection status is reflected in the icon below.
  }, [live.connected]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">告警中心</h2>
          <p className="text-sm text-muted-foreground">实时事件流 + 规则触发</p>
        </div>
        <div className="flex items-center gap-2">
          <Radio className={cn("h-4 w-4", live.connected ? "text-emerald-500" : "text-muted-foreground")} />
          <span className="text-xs text-muted-foreground">{live.connected ? "已连接 SSE" : "未连接"}</span>
          <Button variant="ghost" size="sm" onClick={() => events.refetch()}>
            <RotateCcw className="mr-2 h-3 w-3" />
            刷新
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">规则</CardTitle>
            <CardDescription>60s 滑动窗口</CardDescription>
          </CardHeader>
          <CardContent>
            {rules.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <ul className="space-y-2 text-sm">
                {rules.data?.rules.map((r) => {
                  const Icon = SEV_ICON[r.severity as keyof typeof SEV_ICON] ?? Info;
                  return (
                    <li key={r.id} className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <Icon className="h-3.5 w-3.5" />
                        <span className="font-mono text-xs">{r.id}</span>
                      </span>
                      <Badge variant={r.severity === "critical" ? "destructive" : "secondary"}>
                        {r.event} ≥ {r.threshold}
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">计数器</CardTitle>
            <CardDescription>当前 buffer 大小</CardDescription>
          </CardHeader>
          <CardContent>
            {rules.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <ul className="space-y-2 text-sm">
                {Object.entries(rules.data?.event_counters ?? {}).map(([k, v]) => (
                  <li key={k} className="flex items-center justify-between">
                    <span className="font-mono text-xs">{k}</span>
                    <Badge variant="secondary">{v}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">SSE 缓冲</CardTitle>
            <CardDescription>最近 200 条事件</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <Bell className="h-8 w-8 text-muted-foreground" />
              <div>
                <div className="text-2xl font-bold">{live.events.length}</div>
                <div className="text-xs text-muted-foreground">前端已接收事件</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>最近事件</CardTitle>
          <CardDescription>最近 50 条，按时间倒序</CardDescription>
        </CardHeader>
        <CardContent>
          {events.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : events.isError ? (
            <p className="py-8 text-center text-sm text-destructive">无法连接后端</p>
          ) : !events.data?.items?.length ? (
            <p className="py-8 text-center text-sm text-muted-foreground">暂无事件</p>
          ) : (
            <ul className="space-y-2">
              {events.data.items.map((it, i) => {
                const Icon = it.ok === false ? AlertCircle : it.topic === "risk" ? AlertTriangle : Info;
                return (
                  <li key={i}>
                    <div className="flex items-center justify-between rounded-md border p-3 text-sm">
                      <span className="flex items-center gap-2">
                        <Icon
                          className={cn(
                            "h-4 w-4",
                            it.ok === false ? "text-destructive" : "text-muted-foreground",
                          )}
                        />
                        <span className="font-mono text-xs">topic={it.topic ?? "-"}</span>
                        {it.task_id !== undefined && (
                          <span className="font-mono text-xs text-muted-foreground">
                            task={it.task_id}
                          </span>
                        )}
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {it.ts ? new Date(it.ts * 1000).toLocaleTimeString() : "-"}
                      </span>
                    </div>
                    {i < events.data!.items.length - 1 && <Separator className="my-1" />}
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}