import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { LineChart, BarChart3, GitBranch, Flame } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import api from "@/lib/api";
import { formatNumber } from "@/lib/utils";

interface KpiResp {
  pv_today: number;
  uv_today: number;
  pv_uv_ratio: number | null;
  conversions_today: number;
  funnel: { stage: string; count: number }[];
  source?: string;
}

export default function AnalyticsOverview() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "kpis"],
    queryFn: async () => (await api.get<KpiResp>("/v1/lakehouse/kpis")).data,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">数据分析 · 今日概览</h2>
          <p className="text-sm text-muted-foreground">lakehouse-api · 每 60s 刷新</p>
        </div>
        {data?.source && (
          <Badge variant={data.source === "trino" ? "success" : "secondary"}>
            data: {data.source}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="mt-3 h-8 w-20" />
              </CardContent>
            </Card>
          ))
        ) : isError ? (
          <Card className="col-span-4 border-destructive/50 bg-destructive/5">
            <CardHeader>
              <CardTitle className="text-destructive">无法连接 lakehouse-api</CardTitle>
              <CardDescription>
                请确认 lakehouse-api 已启动 (默认 :8091)。
              </CardDescription>
            </CardHeader>
          </Card>
        ) : data ? (
          [
            { label: "今日 PV", value: data.pv_today },
            { label: "今日 UV", value: data.uv_today },
            { label: "PV/UV 比", value: data.pv_uv_ratio ?? 0, decimals: 2 },
            { label: "今日转化", value: data.conversions_today },
          ].map((k) => (
            <Card key={k.label}>
              <CardContent className="p-6">
                <div className="text-xs text-muted-foreground">{k.label}</div>
                <div className="mt-2 text-3xl font-bold tabular-nums">
                  {formatNumber(k.value)}
                </div>
              </CardContent>
            </Card>
          ))
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <GitBranch className="h-4 w-4" />
              转化漏斗
            </CardTitle>
            <CardDescription>4 阶段漏斗</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild className="w-full">
              <Link to="/analytics/funnel">查看完整漏斗</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Flame className="h-4 w-4" />
              Top-N 热榜
            </CardTitle>
            <CardDescription>Top 热门 item</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild className="w-full">
              <Link to="/analytics/top-items">查看 Top-Items</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <LineChart className="h-4 w-4" />
              PV 时序
            </CardTitle>
            <CardDescription>最近 14 天</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild className="w-full">
              <Link to="/analytics/pv-uv">查看时序图</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4" />
              快速入口
            </CardTitle>
            <CardDescription>组合视图</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" asChild>
                <Link to="/analytics/pv-uv">PV vs UV</Link>
              </Button>
              <Button size="sm" variant="secondary" asChild>
                <Link to="/analytics/funnel">漏斗</Link>
              </Button>
              <Button size="sm" variant="secondary" asChild>
                <Link to="/analytics/top-items">热榜</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}