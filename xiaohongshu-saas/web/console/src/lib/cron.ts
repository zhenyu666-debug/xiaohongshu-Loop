/**
 * Tiny cron expression humanizer.
 * Supports 5-field cron: minute hour day-of-month month day-of-week
 * Returns best-effort Chinese description, falls back to the raw expression.
 */
export function describeCron(expr: string | null | undefined): string {
  if (!expr || typeof expr !== "string") return "-";
  const trimmed = expr.trim();
  if (!trimmed) return "-";

  const parts = trimmed.split(/\s+/);
  if (parts.length !== 5) return trimmed;

  const [min, hour, dom, mon, dow] = parts;

  if (trimmed === "@hourly" || min !== "*" && hour === "*" && dom === "*" && mon === "*" && dow === "*") {
    return `每小时 ${min} 分`;
  }
  if (trimmed === "@daily" || (min !== "*" && hour !== "*" && dom === "*" && mon === "*" && dow === "*")) {
    return `每天 ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  }
  if (trimmed === "@weekly" && dow !== "*") {
    return `每周${dow} ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  }
  if (dom !== "*" && mon === "*" && dow === "*") {
    return `每月${dom}日 ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  }
  if (dow !== "*") {
    return `每周${dow} ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  }
  return trimmed;
}