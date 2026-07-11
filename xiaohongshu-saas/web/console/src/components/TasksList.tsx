import { useState, useMemo } from "react";
import { Play, Pause, Trash2, Moon, Sun, Filter } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge-extra";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUIStore } from "@/hooks/useUIStore";
import type { TaskOut } from "@/types/api";

const SERVICE_FILTERS = [
  { label: "全部", value: null },
  { label: "xhs", value: "xhs" },
  { label: "pbp", value: "pbp" },
  { label: "lakehouse", value: "lakehouse" },
];

function getStatusBadge(status: TaskOut["status"]) {
  switch (status) {
    case "active":
      return <Badge variant="success">运行中</Badge>;
    case "paused":
      return <Badge variant="warning">已暂停</Badge>;
    default:
      return <Badge variant="secondary">草稿</Badge>;
  }
}

function getKindLabel(kind: TaskOut["kind"]) {
  switch (kind) {
    case "loop":
      return "循环";
    case "schedule":
      return "定时";
    default:
      return "单次";
  }
}

export function TasksList() {
  const { darkMode, setDarkMode, logFilter, setLogFilter } = useUIStore();
  const [tasks] = useState<TaskOut[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTasks = useMemo(() => {
    return tasks.filter(
      (task) =>
        task.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        (!logFilter || task.channel.includes(logFilter))
    );
  }, [tasks, searchQuery, logFilter]);

  return (
    <Card className={`${darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}`}>
      <CardHeader className="pb-2">
        <div className="flex flex-row items-center justify-between mb-3">
          <CardTitle className={`text-base ${darkMode ? "text-slate-100" : "text-slate-900"}`}>
            任务列表
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
              className={darkMode ? "text-slate-300 hover:text-slate-100" : "text-slate-600 hover:text-slate-900"}
            >
              {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Input
              placeholder="搜索任务..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={darkMode ? "bg-slate-800 border-slate-700 text-slate-200" : ""}
            />
          </div>
          <div className="flex items-center gap-1">
            <Filter className={`h-4 w-4 ${darkMode ? "text-slate-400" : "text-slate-500"}`} />
            {SERVICE_FILTERS.map((filter) => (
              <Button
                key={filter.label}
                variant={logFilter === filter.value ? "default" : "outline"}
                size="sm"
                onClick={() => setLogFilter(filter.value)}
                className={`h-8 text-xs ${
                  logFilter === filter.value ? "" : darkMode ? "border-slate-700 text-slate-300" : ""
                }`}
              >
                {filter.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {filteredTasks.length === 0 ? (
          <p className={`text-sm ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
            {searchQuery || logFilter ? "没有匹配的任务" : "暂无任务"}
          </p>
        ) : (
          <div className="space-y-2">
            {filteredTasks.map((task) => (
              <div
                key={task.id}
                className={`flex items-center justify-between p-3 rounded-lg gap-4 ${
                  darkMode ? "bg-slate-800/50 hover:bg-slate-800" : "bg-slate-50 hover:bg-slate-100"
                } transition-colors`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium ${darkMode ? "text-slate-200" : "text-slate-900"}`}>
                      {task.name}
                    </span>
                    {getStatusBadge(task.status)}
                    <Badge variant="outline" className={darkMode ? "border-slate-600 text-slate-400" : ""}>
                      {getKindLabel(task.kind)}
                    </Badge>
                  </div>
                  <div className={`text-xs mt-1 ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
                    {task.channel} · 账号: {task.account_ids.length}个
                    {task.next_run_at && ` · 下次: ${new Date(task.next_run_at).toLocaleString("zh-CN")}`}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className={darkMode ? "text-slate-400 hover:text-slate-200" : ""}
                  >
                    {task.status === "active" ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className={darkMode ? "text-slate-400 hover:text-red-400" : "text-red-500"}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
