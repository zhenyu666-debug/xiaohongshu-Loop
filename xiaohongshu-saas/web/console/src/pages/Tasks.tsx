import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Play, Pause } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { Task } from "@/types/api";

export default function Tasks() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["tasks"],
    queryFn: async () => (await api.get<Task[]>("/scheduler/tasks/")).data,
  });

  const triggerMut = useMutation({
    mutationFn: async (id: number) => api.post(`/scheduler/tasks/${id}/run/`),
    onSuccess: () => {
      toast.success("任务已触发");
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (e: Error) => toast.error(`触发失败: ${e.message}`),
  });

  const toggleMut = useMutation({
    mutationFn: async (t: Task) => api.patch(`/scheduler/tasks/${t.id}/`, { enabled: !t.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">定时任务</h2>
        <p className="text-sm text-muted-foreground">查看调度任务、启停与手动触发</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务列表</CardTitle>
          <CardDescription>{data?.length ?? 0} 个任务</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p className="py-8 text-center text-sm text-destructive">加载失败</p>
          ) : !data || data.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">暂无任务</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>平台</TableHead>
                  <TableHead>Cron</TableHead>
                  <TableHead>上次运行</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-mono text-xs">{t.id}</TableCell>
                    <TableCell>{t.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{t.channel}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{t.schedule}</TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(t.last_run, "从未")}</TableCell>
                    <TableCell>
                      <Badge variant={t.enabled ? "success" : "secondary"}>
                        {t.enabled ? "启用" : "停用"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => toggleMut.mutate(t)}
                          disabled={toggleMut.isPending}
                        >
                          {t.enabled ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                          {t.enabled ? "停用" : "启用"}
                        </Button>
                        <Button
                          size="sm"
                          disabled={triggerMut.isPending}
                          onClick={() => triggerMut.mutate(t.id)}
                        >
                          立即执行
                        </Button>
                      </div>
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