import { useState, useEffect, useCallback } from "react";

export interface SSEEvent {
  type: string;
  data: unknown;
  timestamp: string;
}

export function useSSE(url: string, enabled: boolean = true) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let eventSource: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        setConnected(true);
        setError(null);
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setEvents((prev) => [...prev.slice(-99), { type: "message", data, timestamp: new Date().toISOString() }]);
        } catch {
          setEvents((prev) => [...prev.slice(-99), { type: "message", data: event.data, timestamp: new Date().toISOString() }]);
        }
      };

      eventSource.onerror = () => {
        setConnected(false);
        setError("SSE connection lost");
        eventSource?.close();
        reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      eventSource?.close();
    };
  }, [url, enabled]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, error, clearEvents };
}
