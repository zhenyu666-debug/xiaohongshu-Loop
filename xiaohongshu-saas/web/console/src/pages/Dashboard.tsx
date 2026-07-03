import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/utils";
import type { DashboardSummary } from "@/types/api";

export default function Dashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => (await api.get<DashboardSummary>("/dashboard/summary")).data,
    refetchInterval: 30_000,
  });

  if (isError) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="text-destructive">无法连接后端</CardTitle>
          <CardDescription>{(error as Error)?.message ?? "未知错误"}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const kpis = data
    ? [
        { label: "账号总数", value: data.total_accounts },
        { label: "活跃账号", value: data.active_accounts },
        { label: "任务总数", value: data.total_tasks },
        { label: "待执行", value: data.pending_tasks },
        { label: "执行中", value: data.running_tasks },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">概览</h2>
        <p className="text-sm text-muted-foreground">账号 / 任务 / 发布 实时状态</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        {isLoading
          ? Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="mt-3 h-8 w-12" />
                </CardContent>
              </Card>
            ))
          : kpis.map((k) => (
              <Card key={k.label}>
                <CardContent className="p-6">
                  <div className="text-xs text-muted-foreground">{k.label}</div>
                  <div className="mt-2 text-3xl font-bold tabular-nums">{formatNumber(k.value)}</div>
                </CardContent>
              </Card>
            ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>最近发布</CardTitle>
          <CardDescription>最近 20 条发布记录，每 30s 自动刷新</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.recent_publishes.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">暂无发布记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>平台</TableHead>
                  <TableHead>标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_publishes.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <Badge variant="outline">{p.channel}</Badge>
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate" title={p.title}>
                      {p.title}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          p.status === "success"
                            ? "success"
                            : p.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {p.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(p.created_at)}</TableCell>
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