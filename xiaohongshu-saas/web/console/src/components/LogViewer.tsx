import { useState, useEffect, useRef, useMemo } from "react";
import { Moon, Sun, Download } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/hooks/useUIStore";

const SERVICE_PATTERNS: Record<string, RegExp> = {
  xhs: /\[xhs[-_\s]?saas\]|\[xhs\]/i,
  pbp: /\[pbp[-_\s]?api\]|\[pbp\]/i,
  lakehouse: /\[lakehouse[-_\s]?api\]|\[lakehouse\]/i,
};

const SERVICE_COLORS: Record<string, string> = {
  xhs: "#34d399",
  pbp: "#38bdf8",
  lakehouse: "#a78bfa",
};

export function LogViewer() {
  const { darkMode, setDarkMode, logFilter, setLogFilter: _setLogFilter } = useUIStore();
  const [logs, setLogs] = useState<Array<{ ts: string; msg: string; cls: string }>>([]);
  const [filter, setFilter] = useState<string>("");
  const logContainerRef = useRef<HTMLPreElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Demo logs for preview
  useEffect(() => {
    const demoLogs = [
      { ts: new Date().toISOString(), msg: "[xhs-saas] Application startup complete. Uvicorn running on http://127.0.0.1:8080", cls: "s-xhs" },
      { ts: new Date().toISOString(), msg: "[pbp-api] Service started on port 8090", cls: "s-pbp" },
      { ts: new Date().toISOString(), msg: "[lakehouse-api] Service started on port 8091", cls: "s-lake" },
    ];
    setLogs(demoLogs);
  }, []);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesService = !filter || log.cls.includes(filter.toLowerCase());
      const matchesText = !logFilter || log.msg.toLowerCase().includes(logFilter.toLowerCase());
      return matchesService && matchesText;
    });
  }, [logs, filter, logFilter]);

  const handleScroll = () => {
    if (logContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isAtBottom);
    }
  };

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  return (
    <Card className={`${darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}`}>
      <CardHeader className="pb-2">
        <div className="flex flex-row items-center justify-between">
          <CardTitle className={`text-base ${darkMode ? "text-slate-100" : "text-slate-900"}`}>
            运行日志
          </CardTitle>
          <div className="flex items-center gap-2">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className={`h-8 px-2 rounded border text-xs ${
                darkMode
                  ? "bg-slate-800 border-slate-700 text-slate-300"
                  : "bg-white border-slate-200 text-slate-700"
              }`}
            >
              <option value="">全部服务</option>
              <option value="xhs">xhs-saas</option>
              <option value="pbp">pbp-api</option>
              <option value="lake">lakehouse-api</option>
            </select>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
              className={darkMode ? "text-slate-300 hover:text-slate-100" : "text-slate-600 hover:text-slate-900"}
            >
              {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                const text = filteredLogs.map((l) => `[${l.ts}] ${l.msg}`).join("\n");
                const blob = new Blob([text], { type: "text/plain" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `xhs-saas-logs-${new Date().toISOString().slice(0, 10)}.txt`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className={darkMode ? "text-slate-300 hover:text-slate-100" : "text-slate-600 hover:text-slate-900"}
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <pre
          ref={logContainerRef}
          onScroll={handleScroll}
          className={`h-64 overflow-auto rounded-lg p-3 font-mono text-xs leading-relaxed ${
            darkMode ? "bg-slate-950 text-slate-300" : "bg-slate-50 text-slate-700"
          }`}
        >
          {filteredLogs.map((log, idx) => {
            const serviceMatch = Object.entries(SERVICE_PATTERNS).find(([, re]) => re.test(log.msg));
            const color = serviceMatch ? SERVICE_COLORS[serviceMatch[0]] : undefined;
            return (
              <div key={idx} className={log.cls}>
                <span className={`${darkMode ? "text-slate-500" : "text-slate-400"} mr-2`}>
                  {new Date(log.ts).toLocaleTimeString("zh-CN")}
                </span>
                <span style={color ? { color } : undefined}>{log.msg}</span>
              </div>
            );
          })}
        </pre>
      </CardContent>
    </Card>
  );
}
