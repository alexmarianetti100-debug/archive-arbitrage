import { useState, useEffect, useRef, useCallback } from 'react';

export interface SSEEvent {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

interface UseSSEOptions {
  url: string | null;  // null = don't connect
  onEvent?: (event: SSEEvent) => void;
}

interface UseSSEReturn {
  events: SSEEvent[];
  connected: boolean;
  error: string | null;
  clearEvents: () => void;
}

export function useSSE({ url, onEvent }: UseSSEOptions): UseSSEReturn {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!url) {
      setConnected(false);
      return;
    }

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (msg) => {
      try {
        const parsed: SSEEvent = JSON.parse(msg.data);
        setEvents((prev) => [...prev, parsed]);
        onEventRef.current?.(parsed);

        // Close on terminal events
        if (['scrape:complete', 'scrape:error', 'scrape:cancelled'].includes(parsed.type)) {
          es.close();
          setConnected(false);
        }
      } catch {
        // Ignore parse errors (e.g., keepalive comments)
      }
    };

    es.onerror = () => {
      setError('Connection lost');
      setConnected(false);
      es.close();
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [url]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, error, clearEvents };
}
