import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  LabelList,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import api from "@/lib/api";
import { formatNumber } from "@/lib/utils";

interface FunnelResp {
  items: { stage: string; count: number }[];
}

const STAGE_COLORS = ["#22d3ee", "#10b981", "#f59e0b", "#ef4444"];

export default function AnalyticsFunnel() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "funnel"],
    queryFn: async () => (await api.get<FunnelResp>("/v1/lakehouse/funnel")).data,
    refetchInterval: 60_000,
  });

  const items = (data?.items ?? []).slice().reverse();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">转化漏斗</h2>
        <p className="text-sm text-muted-foreground">lakehouse-api · 4 阶段漏斗</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>漏斗图</CardTitle>
          <CardDescription>访问 → 浏览 → 点击 → 转化</CardDescription>
        </CardHeader>
        <CardContent className="h-[440px]">
          {isLoading || !data ? (
            <Skeleton className="h-full w-full" />
          ) : isError ? (
            <p className="flex h-full items-center justify-center text-sm text-destructive">
              无法连接 lakehouse-api
            </p>
          ) : items.length === 0 ? (
            <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={items} layout="vertical" margin={{ top: 16, right: 64, bottom: 16, left: 64 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
                <XAxis type="number" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis
                  dataKey="stage"
                  type="category"
                  tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
                  width={80}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 6,
                  }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {items.map((_, i) => (
                    <Cell key={i} fill={STAGE_COLORS[i % STAGE_COLORS.length]} />
                  ))}
                  <LabelList
                    dataKey="count"
                    position="right"
                    style={{ fontSize: 11, fill: "hsl(var(--foreground))" }}
                    formatter={(v: number) => formatNumber(v)}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}