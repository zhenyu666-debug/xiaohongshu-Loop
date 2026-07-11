import { useState, useEffect, useCallback } from "react";

export interface SSEEvent {
  type: string;
  data: unknown;
  timestamp: string;
}

export interface UseSSEOptions {
  enabled?: boolean;
  onEvent?: (event: SSEEvent) => void;
}

export function useSSE<T = unknown>(url: string, options: boolean | UseSSEOptions = true) {
  const enabled = typeof options === "boolean" ? options : (options.enabled ?? true);
  const onEvent = typeof options === "object" ? options.onEvent : undefined;

  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;

    if (typeof EventSource === "undefined") {
      setError("EventSource is not available in this environment");
      return;
    }

    let eventSource: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        setConnected(true);
        setError(null);
      };

      eventSource.onmessage = (event) => {
        let parsed: T | string = event.data as T;
        try {
          parsed = JSON.parse(event.data) as T;
        } catch {
          parsed = event.data;
        }
        const evt: SSEEvent = {
          type: "message",
          data: parsed,
          timestamp: new Date().toISOString(),
        };
        setEvents((prev) => [...prev.slice(-99), evt]);
        onEvent?.(evt);
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
  }, [url, enabled, onEvent]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, error, clearEvents };
}
