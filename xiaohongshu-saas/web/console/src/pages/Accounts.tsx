import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";
import type { Account } from "@/types/api";

export default function Accounts() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<Account[]>("/accounts")).data,
  });

  const loginMut = useMutation({
    mutationFn: async (id: string) => api.post(`/accounts/${id}/login`),
    onSuccess: () => {
      toast.success("登录任务已启动");
      qc.invalidateQueries({ queryKey: ["accounts"] });
    },
    onError: (e: Error) => toast.error(`登录失败: ${e.message}`),
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">账号管理</h2>
        <p className="text-sm text-muted-foreground">查看账号池状态并触发扫码登录</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>账号列表</CardTitle>
          <CardDescription>{data?.length ?? 0} 个账号</CardDescription>
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
            <p className="py-8 text-center text-sm text-muted-foreground">暂无账号</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>昵称</TableHead>
                  <TableHead>平台</TableHead>
                  <TableHead>阶段</TableHead>
                  <TableHead>Cookie</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-mono text-xs">{a.id}</TableCell>
                    <TableCell>{a.nickname}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{a.channel}</Badge>
                    </TableCell>
                    <TableCell>{a.stage}</TableCell>
                    <TableCell>
                      <Badge variant={a.cookies_valid ? "success" : "destructive"}>
                        {a.cookies_valid ? "有效" : "无效"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={loginMut.isPending}
                        onClick={() => loginMut.mutate(a.id)}
                      >
                        {loginMut.isPending ? "启动中..." : "扫码登录"}
                      </Button>
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