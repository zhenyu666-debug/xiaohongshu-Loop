import { useEffect, useRef, useState } from "react";

export interface SSEEvent<T = unknown> {
  data: T;
  raw: string;
  event: string;
  id?: string;
}

export function useSSE<T = unknown>(url: string | null, opts?: { onEvent?: (e: SSEEvent<T>) => void }) {
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<Error | null>(null);
  const [events, setEvents] = useState<SSEEvent<T>[]>([]);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  useEffect(() => {
    if (!url) return;
    const ctrl = new AbortController();
    let alive = true;

    (async () => {
      while (alive) {
        try {
          const r = await fetch(url, {
            headers: { Accept: "text/event-stream" },
            signal: ctrl.signal,
          });
          if (!r.ok || !r.body) throw new Error(`SSE ${r.status}`);
          setConnected(true);
          setLastError(null);
          const reader = r.body.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          while (alive) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const blocks = buf.split("\n\n");
            buf = blocks.pop() ?? "";
            for (const block of blocks) {
              if (!block) continue;
              let event = "message";
              let data = "";
              const lines = block.split("\n");
              for (const line of lines) {
                if (line.startsWith(":")) continue;
                if (line.startsWith("data:")) data += line.slice(5).trim();
                else if (line.startsWith("event:")) event = line.slice(6).trim();
              }
              if (!data) continue;
              let parsed: unknown = data;
              try {
                parsed = JSON.parse(data);
              } catch {
                /* leave as string */
              }
              const evt: SSEEvent<T> = { data: parsed as T, raw: data, event };
              setEvents((prev) => [evt, ...prev].slice(0, 200));
              optsRef.current?.onEvent?.(evt);
            }
          }
        } catch (e) {
          if (!alive) break;
          setConnected(false);
          setLastError(e instanceof Error ? e : new Error(String(e)));
          await new Promise((res) => setTimeout(res, 2000));
        }
      }
    })();

    return () => {
      alive = false;
      ctrl.abort();
      setConnected(false);
    };
  }, [url]);

  return { connected, lastError, events };
}