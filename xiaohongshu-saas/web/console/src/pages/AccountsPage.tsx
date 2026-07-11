import { TabNav } from "@/components/layout/TabNav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge-extra";
import { useUIStore } from "@/hooks/useUIStore";

const DEMO_ACCOUNTS = [
  { id: "acc_001", nickname: "小红书创作者A", channel: "xiaohongshu", stage: "normal" },
  { id: "acc_002", nickname: "小红书创作者B", channel: "xiaohongshu", stage: "warmup" },
];

export function AccountsPage() {
  const { darkMode } = useUIStore();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">账号管理</h2>
        <TabNav />
      </div>

      <div className="flex justify-end">
        <Button className={darkMode ? "bg-slate-800 hover:bg-slate-700" : ""}>
          + 添加账号
        </Button>
      </div>

      <div className="grid gap-4">
        {DEMO_ACCOUNTS.map((account) => (
          <Card key={account.id} className={darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className={`text-sm ${darkMode ? "text-slate-200" : "text-slate-800"}`}>
                  {account.nickname}
                </CardTitle>
                <Badge
                  variant={
                    account.stage === "normal"
                      ? "success"
                      : account.stage === "warmup"
                      ? "warning"
                      : "secondary"
                  }
                >
                  {account.stage === "normal" ? "正常" : account.stage === "warmup" ? "暖机中" : account.stage}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className={`text-xs ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
                渠道: {account.channel} | ID: {account.id}
              </p>
              <div className="flex gap-2 mt-3">
                <Button size="sm" variant="outline" className={darkMode ? "border-slate-700" : ""}>
                  编辑
                </Button>
                <Button size="sm" variant="outline" className={darkMode ? "border-slate-700" : ""}>
                  重新登录
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
