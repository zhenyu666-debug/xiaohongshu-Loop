import { TabNav } from "@/components/layout/TabNav";
import { useUIStore } from "@/hooks/useUIStore";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Moon, Sun } from "lucide-react";

export function SettingsPage() {
  const { darkMode, setDarkMode } = useUIStore();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">设置</h2>
        <TabNav />
      </div>

      <Card className={darkMode ? "bg-slate-900 border-slate-800" : "bg-white"}>
        <CardContent className="pt-4 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className={`font-medium ${darkMode ? "text-slate-200" : "text-slate-800"}`}>
                深色模式
              </p>
              <p className={`text-sm ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
                切换控制台主题
              </p>
            </div>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
              className={darkMode ? "border-slate-700" : ""}
            >
              {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>

          <div className="border-t border-slate-700 pt-4">
            <p className={`font-medium ${darkMode ? "text-slate-200" : "text-slate-800"}`}>
              关于
            </p>
            <p className={`text-sm ${darkMode ? "text-slate-500" : "text-slate-400"}`}>
              xhs-saas-console v1.1.0
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
