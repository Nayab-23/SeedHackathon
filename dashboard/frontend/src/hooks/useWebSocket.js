import { useEffect, useRef, useState, useCallback } from 'react';
import { getWsUrl } from '../api';

export default function useWebSocket(onMessage, maxRetries = 10) {
  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const url = getWsUrl();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      if (retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current += 1;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onMessage, maxRetries]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { connected };
}
