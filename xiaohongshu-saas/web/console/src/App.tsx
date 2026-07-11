import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConsoleLayout } from "@/components/layout/ConsoleLayout";
import { Dashboard } from "@/pages/Dashboard";
import { AccountsPage } from "@/pages/AccountsPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { SettingsPage } from "@/pages/SettingsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ConsoleLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="accounts" element={<AccountsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
