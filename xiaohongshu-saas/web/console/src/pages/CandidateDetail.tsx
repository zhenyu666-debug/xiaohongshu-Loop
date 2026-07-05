import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";

interface CandidateDetail {
  id: number;
  rank: number;
  score: number;
  smiles: string;
  [descriptor: string]: number | string;
}

export default function CandidateDetail() {
  const { id } = useParams<{ id: string }>();
  const cid = Number(id);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["candidates", "detail", cid],
    queryFn: async () => (await api.get<CandidateDetail>(`/v1/pbp/candidates/${cid}`)).data,
    enabled: Number.isFinite(cid) && cid > 0,
  });

  if (!Number.isFinite(cid) || cid <= 0) {
    return <p className="text-sm text-destructive">无效的候选 ID</p>;
  }

  const descriptors = data
    ? Object.entries(data).filter(
        ([k, v]) => !["id", "rank", "score", "smiles"].includes(k) && typeof v === "number",
      )
    : [];

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to="/candidates">
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回列表
        </Link>
      </Button>

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : isError ? (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive">加载失败</CardTitle>
            <CardDescription>{(error as Error)?.message ?? "未知错误"}</CardDescription>
          </CardHeader>
        </Card>
      ) : !data ? (
        <p className="text-sm text-muted-foreground">候选不存在</p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>候选 #{data.rank}</CardTitle>
                  <CardDescription>
                    ID {data.id} · SMILES <span className="font-mono text-xs">{data.smiles}</span>
                  </CardDescription>
                </div>
                <Badge variant="success" className="text-base">
                  score = {Number(data.score).toFixed(4)}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                排名越靠前分数越高，分数 ≥ 0.7 被视为强候选。
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>描述符分解</CardTitle>
              <CardDescription>{descriptors.length} 个 descriptor_* 字段</CardDescription>
            </CardHeader>
            <CardContent>
              {descriptors.length === 0 ? (
                <p className="py-4 text-sm text-muted-foreground">无描述符数据</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>名称</TableHead>
                      <TableHead className="text-right">数值</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {descriptors.map(([k, v]) => (
                      <TableRow key={k}>
                        <TableCell className="font-mono text-xs">{k}</TableCell>
                        <TableCell className="text-right font-mono">{Number(v).toFixed(4)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}