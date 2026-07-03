import { useEffect, useState } from "react";
import api from "../api";

interface Task {
  id: number;
  name: string;
  channel: string;
  schedule: string;
  enabled: boolean;
  last_run: string | null;
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [running, setRunning] = useState<number | null>(null);

  const load = () => api.get<Task[]>("/scheduler/tasks/").then((r) => setTasks(r.data));

  useEffect(() => { load(); }, []);

  const trigger = async (id: number) => {
    setRunning(id);
    try {
      await api.post(`/scheduler/tasks/${id}/run/`);
      await load();
    } finally {
      setRunning(null);
    }
  };

  const toggle = async (task: Task) => {
    await api.patch(`/scheduler/tasks/${task.id}/`, { enabled: !task.enabled });
    await load();
  };

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>定时任务</h2>
      <div style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,.1)", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f9fafb", textAlign: "left" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>名称</th>
              <th style={{ padding: "12px 16px" }}>平台</th>
              <th style={{ padding: "12px 16px" }}>Cron</th>
              <th style={{ padding: "12px 16px" }}>上次运行</th>
              <th style={{ padding: "12px 16px" }}>状态</th>
              <th style={{ padding: "12px 16px" }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#888" }}>
                  暂无任务
                </td>
              </tr>
            ) : (
              tasks.map((t) => (
                <tr key={t.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "12px 16px" }}>{t.id}</td>
                  <td style={{ padding: "12px 16px" }}>{t.name}</td>
                  <td style={{ padding: "12px 16px" }}>{t.channel}</td>
                  <td style={{ padding: "12px 16px", fontFamily: "monospace", fontSize: 13 }}>{t.schedule}</td>
                  <td style={{ padding: "12px 16px", color: "#888" }}>
                    {t.last_run ? new Date(t.last_run).toLocaleString("zh-CN") : "从未"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={t.enabled}
                        onChange={() => toggle(t)}
                        style={{ width: 16, height: 16 }}
                      />
                      {t.enabled ? "启用" : "停用"}
                    </label>
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <button
                      onClick={() => trigger(t.id)}
                      disabled={running === t.id}
                      style={{
                        padding: "6px 16px",
                        borderRadius: 6,
                        border: "none",
                        background: running === t.id ? "#d1d5db" : "#1a1a1a",
                        color: "#fff",
                        cursor: running === t.id ? "not-allowed" : "pointer",
                        fontSize: 13,
                      }}
                    >
                      {running === t.id ? "运行中..." : "立即执行"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
