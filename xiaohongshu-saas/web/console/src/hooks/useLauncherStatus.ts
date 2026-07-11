import { useState, useEffect } from "react";
import type { LauncherSnapshot } from "../types/api";

const STATUS_URL = "http://127.0.0.1:8765/status";

export function useLauncherStatus(pollInterval: number = 2000) {
  const [status, setStatus] = useState<LauncherSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const fetchStatus = async () => {
      try {
        const resp = await fetch(STATUS_URL);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data: LauncherSnapshot = await resp.json();
        if (mounted) setStatus(data);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Unknown error");
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, pollInterval);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [pollInterval]);

  return { status, error };
}
