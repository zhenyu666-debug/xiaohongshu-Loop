import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";

interface TopResp {
  metric: string;
  items: { item: string; count: number }[];
}

export default function AnalyticsTopItems() {
  const [metric, setMetric] = useState<"pv" | "uv" | "conversions">("pv");
  const [limit, setLimit] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", "top-items", metric, limit],
    queryFn: async () =>
      (await api.get<TopResp>(`/v1/lakehouse/top-items?metric=${metric}&limit=${limit}`)).data,
    refetchInterval: 60_000,
  });

  const exportCsv = () => {
    if (!data?.items?.length) return;
    const csv = ["rank,item,count", ...data.items.map((it, i) => `${i + 1},${it.item},${it.count}`)].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `top-items-${metric}-${limit}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Top-N 热榜</h2>
          <p className="text-sm text-muted-foreground">lakehouse-api · 按 {metric.toUpperCase()} 排序</p>
        </div>
        <Button variant="outline" onClick={exportCsv} disabled={!data?.items?.length}>
          <Download className="mr-2 h-4 w-4" />
          导出 CSV
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">参数</CardTitle>
          <CardDescription>选择指标 + 限制</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {(["pv", "uv", "conversions"] as const).map((m) => (
              <Button
                key={m}
                size="sm"
                variant={metric === m ? "default" : "outline"}
                onClick={() => setMetric(m)}
              >
                {m}
              </Button>
            ))}
            <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
              Top
              {[5, 10, 20, 50].map((n) => (
                <Button
                  key={n}
                  size="sm"
                  variant={limit === n ? "default" : "outline"}
                  onClick={() => setLimit(n)}
                  className="h-7"
                >
                  {n}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>热门项目</CardTitle>
          <CardDescription>按 count 降序 · {data?.items?.length ?? 0} 条</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p className="py-8 text-center text-sm text-destructive">无法连接 lakehouse-api</p>
          ) : !data?.items?.length ? (
            <p className="py-8 text-center text-sm text-muted-foreground">暂无数据</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead className="text-right">Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((it, i) => (
                  <TableRow key={it.item}>
                    <TableCell className="font-mono">#{i + 1}</TableCell>
                    <TableCell className="font-mono text-xs">{it.item}</TableCell>
                    <TableCell className="text-right">
                      <Badge variant="secondary">{it.count.toLocaleString()}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}