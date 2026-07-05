import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";

interface Top20Item {
  id: number;
  rank: number;
  score: number;
  smiles: string;
  [k: string]: number | string;
}

interface DistBucket {
  bucket: string;
  count: number;
  lo: number;
  hi: number;
}

interface DistResp {
  buckets: number;
  items: DistBucket[];
}

const SCORE_COLORS = ["#10b981", "#059669", "#34d399", "#6ee7b7", "#a7f3d0"];

export default function CandidatesTop20() {
  const top20 = useQuery({
    queryKey: ["candidates", "top20"],
    queryFn: async () => (await api.get<{ items: Top20Item[] }>("/v1/pbp/candidates/top20")).data,
  });

  const dist = useQuery({
    queryKey: ["candidates", "distribution"],
    queryFn: async () => (await api.get<DistResp>("/v1/pbp/candidates/distribution?buckets=12")).data,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Top-20 候选</h2>
        <p className="text-sm text-muted-foreground">donor-screener-pbp · 按分数排序的前 20 个候选</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top-20</CardTitle>
          <CardDescription>Rank 1 = 最佳</CardDescription>
        </CardHeader>
        <CardContent>
          {top20.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : top20.isError ? (
            <p className="py-8 text-center text-sm text-destructive">
              无法连接 pbp-api
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>SMILES</TableHead>
                  <TableHead className="text-right">分数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(top20.data?.items ?? []).map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono">#{c.rank}</TableCell>
                    <TableCell className="font-mono text-xs">
                      <Link to={`/candidates/${c.id}`} className="hover:underline">
                        {c.id}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[320px] truncate font-mono text-xs" title={String(c.smiles)}>
                      {String(c.smiles)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="success">{c.score.toFixed(4)}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>分数分布</CardTitle>
          <CardDescription>所有候选的分数直方图（{dist.data?.buckets ?? 12} 个区间）</CardDescription>
        </CardHeader>
        <CardContent className="h-[320px]">
          {dist.isLoading || !dist.data ? (
            <Skeleton className="h-full w-full" />
          ) : dist.data.items.length === 0 ? (
            <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
              无数据
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dist.data.items}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="bucket"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  interval="preserveStartEnd"
                  angle={-25}
                  height={60}
                />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 6,
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {dist.data.items.map((_, i) => (
                    <Cell key={i} fill={SCORE_COLORS[i % SCORE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}