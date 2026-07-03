export interface Account {
  id: number;
  nickname: string;
  channel: string;
  stage: string;
  proxy: string | null;
  cookies_valid: boolean;
}

export interface Task {
  id: number;
  name: string;
  channel: string;
  schedule: string;
  enabled: boolean;
  last_run: string | null;
}

export interface DashboardSummary {
  total_accounts: number;
  active_accounts: number;
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  recent_publishes: Publish[];
}

export interface Publish {
  id: number;
  channel: string;
  status: string;
  title: string;
  created_at: string;
}

export interface HealthResp {
  status: "ok" | "degraded" | "down";
  services: { name: string; status: "up" | "down"; latency_ms?: number }[];
}

export interface Candidate {
  id: string;
  smiles: string;
  score: number;
  rank: number;
  descriptors: Record<string, number>;
}

export interface CandidateKpi {
  total: number;
  top20_avg_score: number;
  score_min: number;
  score_max: number;
  distribution: { bucket: string; count: number }[];
}

export interface AnalyticsKpi {
  pv_today: number;
  uv_today: number;
  pv_uv_ratio: number;
  conversions_today: number;
  funnel: { stage: string; count: number }[];
}

export interface AnalyticsSeries {
  name: string;
  points: { ts: string; value: number }[];
}