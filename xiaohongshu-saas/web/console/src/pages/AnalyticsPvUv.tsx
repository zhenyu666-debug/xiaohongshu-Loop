import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";

interface SeriesResp {
  name: string;
  points: { ts: string; value: number }[];
  source?: string;
}

const COLORS = { pv: "#22c55e", uv: "#3b82f6", conversions: "#f59e0b" };

export default function AnalyticsPvUv() {
  const [days, setDays] = useState(14);
  const [metrics, setMetrics] = useState<("pv" | "uv" | "conversions")[]>(["pv", "uv"]);

  const seriesQueries = useQuery({
    queryKey: ["analytics", "series", days, metrics],
    queryFn: async () => {
      const results = await Promise.all(
        metrics.map((m) => api.get<SeriesResp>(`/v1/lakehouse/api/series/${m}?days=${days}`).then((r) => r.data)),
      );
      return results;
    },
  });

  const points = (() => {
    const m = seriesQueries.data;
    if (!m || m.length === 0) return [];
    const map = new Map<string, Record<string, string | number>>();
    m.forEach((s) => {
      s.points.forEach((p) => {
        if (!map.has(p.ts)) map.set(p.ts, { ts: p.ts });
        map.get(p.ts)![s.name] = p.value;
      });
    });
    return Array.from(map.values()).sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
  })();

  const toggleMetric = (m: "pv" | "uv" | "conversions") =>
    setMetrics((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">PV / UV 时序</h2>
          <p className="text-sm text-muted-foreground">lakehouse-api · 最近 {days} 天</p>
        </div>
        {seriesQueries.data?.[0]?.source && (
          <Badge variant={seriesQueries.data[0].source === "trino" ? "success" : "secondary"}>
            data: {seriesQueries.data[0].source}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">参数</CardTitle>
          <CardDescription>选择指标和时间范围</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3">
            {(["pv", "uv", "conversions"] as const).map((m) => (
              <Button
                key={m}
                size="sm"
                variant={metrics.includes(m) ? "default" : "outline"}
                onClick={() => toggleMetric(m)}
              >
                {m}
              </Button>
            ))}
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs text-muted-foreground">天数</span>
              <Input
                type="number"
                min={2}
                max={90}
                value={days}
                onChange={(e) => setDays(Math.max(2, Math.min(90, parseInt(e.target.value || "14"))))}
                className="w-24"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>时序图</CardTitle>
          <CardDescription>{metrics.join(" · ")}</CardDescription>
        </CardHeader>
        <CardContent className="h-[420px]">
          {seriesQueries.isLoading || !seriesQueries.data ? (
            <Skeleton className="h-full w-full" />
          ) : seriesQueries.isError ? (
            <p className="flex h-full items-center justify-center text-sm text-destructive">
              无法连接 lakehouse-api
            </p>
          ) : points.length === 0 ? (
            <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="ts" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 6,
                  }}
                />
                <Legend />
                {metrics.map((m) => (
                  <Line
                    key={m}
                    type="monotone"
                    dataKey={m}
                    stroke={COLORS[m]}
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    activeDot={{ r: 4 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}