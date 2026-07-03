import { useEffect, useState } from "react";
import api from "../api";

interface Account {
  id: number;
  nickname: string;
  channel: string;
  stage: string;
  proxy: string | null;
  cookies_valid: boolean;
}

export default function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);

  const load = () => api.get<Account[]>("/accounts/").then((r) => setAccounts(r.data));

  useEffect(() => { load(); }, []);

  const handleLogin = async (id: number) => {
    setLoading(true);
    try {
      await api.post(`/accounts/${id}/login/`);
      await load();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>账号管理</h2>
      <div style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,.1)", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f9fafb", textAlign: "left" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>昵称</th>
              <th style={{ padding: "12px 16px" }}>平台</th>
              <th style={{ padding: "12px 16px" }}>阶段</th>
              <th style={{ padding: "12px 16px" }}>Cookie</th>
              <th style={{ padding: "12px 16px" }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "#888" }}>
                  暂无账号
                </td>
              </tr>
            ) : (
              accounts.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "12px 16px" }}>{a.id}</td>
                  <td style={{ padding: "12px 16px" }}>{a.nickname}</td>
                  <td style={{ padding: "12px 16px" }}>{a.channel}</td>
                  <td style={{ padding: "12px 16px" }}>{a.stage}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: a.cookies_valid ? "#22c55e" : "#ef4444",
                        marginRight: 8,
                      }}
                    />
                    {a.cookies_valid ? "有效" : "无效 / 未登录"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <button
                      onClick={() => handleLogin(a.id)}
                      disabled={loading}
                      style={{
                        padding: "6px 16px",
                        borderRadius: 6,
                        border: "1px solid #d1d5db",
                        background: "#fff",
                        cursor: "pointer",
                        fontSize: 13,
                      }}
                    >
                      扫码登录
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
