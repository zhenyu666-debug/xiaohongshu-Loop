import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import api from "@/lib/api";

interface HealthResp {
  status: "ok" | "degraded" | "down";
  services: { name: string; status: "up" | "down"; latency_ms?: number }[];
}

export function HealthBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ["health", "all"],
    queryFn: async () => (await api.get<HealthResp>("/v1/health/all")).data,
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>检查中</span>
      </div>
    );
  }

  const status = data?.status ?? "down";
  const ok = status === "ok";
  const Icon = ok ? CheckCircle2 : status === "degraded" ? AlertCircle : AlertCircle;
  const color = ok ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400";

  return (
    <div className={cn("flex items-center gap-1.5 text-xs", color)}>
      <Icon className="h-3 w-3" />
      <span className="font-medium">
        {data?.services?.length ?? 0} services · {status}
      </span>
    </div>
  );
}