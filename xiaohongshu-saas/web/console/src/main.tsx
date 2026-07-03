import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { Toaster } from "sonner";
import { router } from "./router";
import { queryClient } from "./lib/queryClient";
import "./index.css";

const savedTheme = (() => {
  try {
    return (localStorage.getItem("xhs.theme") ?? "light") as "light" | "dark";
  } catch {
    return "light";
  }
})();
document.documentElement.classList.toggle("dark", savedTheme === "dark");

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("#root not found");

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  </StrictMode>,
);