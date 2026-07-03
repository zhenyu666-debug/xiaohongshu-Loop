import { useEffect, useState } from "react";
import api from "../api";

interface Summary {
  total_accounts: number;
  active_accounts: number;
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  recent_publishes: {
    id: number;
    channel: string;
    status: string;
    title: string;
    created_at: string;
  }[];
}

export default function Dashboard() {
  const [data, setData] = useState<Summary | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .get<Summary>("/dashboard/summary")
      .then((r) => setData(r.data))
      .catch(() => setErr("无法连接后端服务，请确保 xhs-saas 已启动"));
  }, []);

  if (err) return <p style={{ color: "red" }}>{err}</p>;
  if (!data) return <p>加载中...</p>;

  const kpis = [
    { label: "账号总数", value: data.total_accounts },
    { label: "活跃账号", value: data.active_accounts },
    { label: "任务总数", value: data.total_tasks },
    { label: "待执行", value: data.pending_tasks },
    { label: "执行中", value: data.running_tasks },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>概览</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(160px,1fr))", gap: 16, marginBottom: 32 }}>
        {kpis.map((k) => (
          <div
            key={k.label}
            style={{ background: "#fff", borderRadius: 8, padding: "20px 24px", boxShadow: "0 1px 3px rgba(0,0,0,.1)" }}
          >
            <div style={{ fontSize: 12, color: "#888", marginBottom: 8 }}>{k.label}</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: "#1a1a1a" }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ background: "#fff", borderRadius: 8, padding: 24, boxShadow: "0 1px 3px rgba(0,0,0,.1)" }}>
        <h3 style={{ marginTop: 0, marginBottom: 16 }}>最近发布</h3>
        {data.recent_publishes.length === 0 ? (
          <p style={{ color: "#888" }}>暂无发布记录</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #eee", textAlign: "left" }}>
                <th style={{ padding: "8px 0" }}>平台</th>
                <th style={{ padding: "8px 0" }}>标题</th>
                <th style={{ padding: "8px 0" }}>状态</th>
                <th style={{ padding: "8px 0" }}>时间</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_publishes.map((p) => (
                <tr key={p.id} style={{ borderBottom: "1px solid #f5f5f5" }}>
                  <td style={{ padding: "8px 0" }}>{p.channel}</td>
                  <td style={{ padding: "8px 0", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {p.title}
                  </td>
                  <td style={{ padding: "8px 0" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: 12,
                        fontSize: 12,
                        background: p.status === "success" ? "#dcfce7" : p.status === "failed" ? "#fee2e2" : "#f3f4f6",
                        color: p.status === "success" ? "#16a34a" : p.status === "failed" ? "#dc2626" : "#374151",
                      }}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td style={{ padding: "8px 0", color: "#888" }}>{new Date(p.created_at).toLocaleString("zh-CN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
