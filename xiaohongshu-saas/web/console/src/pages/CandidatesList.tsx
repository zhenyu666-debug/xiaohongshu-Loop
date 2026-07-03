import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Search, BarChart3, Download } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import api from "@/lib/api";
import { useDebounce } from "@/hooks/useDebounce";
import { useVirtualizedList } from "@/hooks/useVirtualizedList";

interface CandidateListItem {
  id: number;
  rank: number;
  score: number;
  smiles: string;
  [k: string]: number | string;
}

interface ListResp {
  total: number;
  offset: number;
  limit: number;
  items: CandidateListItem[];
}

const VIRTUALIZE_THRESHOLD = 200;

export default function CandidatesList() {
  const [search, setSearch] = useState("");
  const [scoreMin, setScoreMin] = useState<string>("");
  const [scoreMax, setScoreMax] = useState<string>("");
  const debouncedSearch = useDebounce(search, 300);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["candidates", "list", scoreMin, scoreMax],
    queryFn: async () => {
      const params: Record<string, string | number> = { limit: 1000 };
      if (scoreMin) params.score_min = parseFloat(scoreMin);
      if (scoreMax) params.score_max = parseFloat(scoreMax);
      const r = await api.get<ListResp>("/v1/pbp/api/candidates", { params });
      return r.data;
    },
  });

  const filtered = (data?.items ?? []).filter((c) => {
    if (!debouncedSearch) return true;
    const q = debouncedSearch.toLowerCase();
    return (
      String(c.id).includes(q) ||
      (c.smiles ?? "").toLowerCase().includes(q) ||
      String(c.rank).includes(q)
    );
  });

  const exportCsv = () => {
    if (!filtered.length) return;
    const keys = Object.keys(filtered[0]);
    const csv = [
      keys.join(","),
      ...filtered.map((c) =>
        keys
          .map((k) => {
            const v = c[k];
            const s = String(v ?? "");
            return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
          })
          .join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `candidates-${filtered.length}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Virtualize when dataset is large
  const useVirtual = filtered.length > VIRTUALIZE_THRESHOLD;
  const virtual = useVirtualizedList(filtered, 36, 600, 8);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">候选列表</h2>
          <p className="text-sm text-muted-foreground">
            donor-screener-pbp · {data?.total ?? 0} 个候选
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={exportCsv} disabled={!filtered.length}>
            <Download className="mr-2 h-4 w-4" />
            导出 CSV
          </Button>
          <Button variant="outline" asChild>
            <Link to="/candidates/top20">
              <BarChart3 className="mr-2 h-4 w-4" />
              Top-20
            </Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>过滤</CardTitle>
          <CardDescription>按 ID / 排名 / SMILES 搜索，按分数范围过滤</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索 id / rank / smiles"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Input
              placeholder="最小分数"
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={scoreMin}
              onChange={(e) => setScoreMin(e.target.value)}
              className="w-32"
            />
            <Input
              placeholder="最大分数"
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={scoreMax}
              onChange={(e) => setScoreMax(e.target.value)}
              className="w-32"
            />
            <Button
              variant="ghost"
              onClick={() => {
                setSearch("");
                setScoreMin("");
                setScoreMax("");
              }}
            >
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>候选</CardTitle>
          <CardDescription>
            显示 {filtered.length} / {data?.total ?? 0}
            {useVirtual && <span className="ml-2 text-xs text-muted-foreground">(virtualized)</span>}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p className="py-8 text-center text-sm text-destructive">
              无法连接 pbp-api（gateway /api/v1/pbp/）。请确认 <code>pbp-api</code> 已启动。
            </p>
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">无匹配候选</p>
          ) : useVirtual ? (
            <div ref={virtual.containerRef} className="relative h-[600px] overflow-auto rounded border">
              <div style={{ height: virtual.totalHeight, position: "relative" }}>
                <div style={{ transform: `translateY(${virtual.offsetY}px)` }}>
                  {virtual.slice.map((c) => (
                    <div
                      key={c.id}
                      className="grid grid-cols-[80px_120px_1fr_120px_100px] items-center gap-2 border-b px-3 text-sm"
                      style={{ height: 36 }}
                    >
                      <span className="font-mono text-xs">#{c.rank}</span>
                      <span className="font-mono text-xs">{c.id}</span>
                      <span className="truncate font-mono text-xs" title={String(c.smiles)}>
                        {String(c.smiles)}
                      </span>
                      <span className="text-right">
                        <Badge variant={c.score >= 0.7 ? "success" : c.score >= 0.5 ? "secondary" : "destructive"}>
                          {c.score.toFixed(4)}
                        </Badge>
                      </span>
                      <Button size="sm" variant="ghost" asChild className="h-7">
                        <Link to={`/candidates/${c.id}`}>详情</Link>
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>SMILES</TableHead>
                  <TableHead className="text-right">分数</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono text-xs">#{c.rank}</TableCell>
                    <TableCell className="font-mono text-xs">{c.id}</TableCell>
                    <TableCell className="max-w-[280px] truncate font-mono text-xs" title={String(c.smiles)}>
                      {String(c.smiles)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant={c.score >= 0.7 ? "success" : c.score >= 0.5 ? "secondary" : "destructive"}>
                        {c.score.toFixed(4)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="ghost" asChild>
                        <Link to={`/candidates/${c.id}`}>详情</Link>
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