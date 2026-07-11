// API types matching backend pydantic schemas

export interface HealthResp {
  services: { name: string; status: "up" | "down"; latency_ms?: number }[];
  [k: string]: unknown;
}

export interface AccountOut {
  id: string;
  tenant_id: string;
  channel: string;
  nickname: string;
  stage: "new" | "warmup" | "normal" | "cooling" | "banned";
  proxy: string | null;
  cookie_path: string | null;
  cookies_valid: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaskOut {
  id: number;
  tenant_id: string;
  name: string;
  channel: string;
  account_ids: string[];
  template_key: string;
  kind: "once" | "loop" | "schedule";
  status: "draft" | "active" | "paused";
  cron: string | null;
  interval_minutes: number | null;
  jitter_minutes: number;
  window_start: string | null;
  window_end: string | null;
  use_ai: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertOut {
  id: number;
  tenant_id: string;
  level: "info" | "warning" | "error";
  message: string;
  resource: string;
  resource_id: string | null;
  created_at: string;
}

export interface PublishResult {
  success: boolean;
  error?: string;
  url?: string;
  published_at?: string;
}

export type ServiceName = "xhs-saas" | "pbp-api" | "lakehouse-api";

export interface ServiceStatus {
  port: number;
  enabled: boolean;
  running: boolean;
  healthy: boolean;
  state: "running" | "stopped" | "disabled";
  last_error: string;
}

export interface LauncherSnapshot {
  console_url: string;
  all_healthy: boolean;
  services: Record<ServiceName, ServiceStatus>;
}

// Back-compat aliases for shorter imports used by older pages.
// Task/TaskOut history: the frontend was originally written against a flatter
// schema with `enabled: boolean`, `schedule: string`, `last_run: string | null`.
// TaskOut (the pydantic mirror) uses `status: "draft" | "active" | "paused"`,
// `cron`, `last_run_at`. Pages still reach into the snake-case names, so
// we alias the old shape here rather than rewrite every page.
export interface Task {
  id: number;
  name: string;
  channel: string;
  schedule: string;
  enabled: boolean;
  last_run: string | null;
  [k: string]: unknown;
}
export type Account = AccountOut;
