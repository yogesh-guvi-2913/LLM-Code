import { useRef, useCallback, useEffect, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

export function useAIChat({ testId, authToken, sessionId, onCodeChanges, onError }) {
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const isClosingRef = useRef(false);
  const pendingMessageRef = useRef(null);
  const onCodeChangesRef = useRef(onCodeChanges);
  const onErrorRef = useRef(onError);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  const streamCallbacksRef = useRef(null);

  useEffect(() => {
    onCodeChangesRef.current = onCodeChanges;
    onErrorRef.current = onError;
  }, [onCodeChanges, onError]);

  const connect = useCallback(() => {
    if (!testId || !authToken) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    isClosingRef.current = false;

    let url = `${WS_BASE_URL}/ws/ai-chat/${testId}?token=${authToken}`;
    if (sessionId) {
      url += `&sessionId=${sessionId}`;
    }
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;

      if (pendingMessageRef.current) {
        ws.send(JSON.stringify(pendingMessageRef.current));
        pendingMessageRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      const { type, content, files, error } = data;
      const cb = streamCallbacksRef.current;

      switch (type) {
        case 'connected':
          setIsConnected(true);
          break;
        case 'text':
          cb?.onText?.(content);
          break;
        case 'code':
          if (files && files.length > 0) {
            onCodeChangesRef.current?.(files);
          }
          break;
        case 'sync':
          cb?.onSync?.(content);
          break;
        case 'done':
          setIsStreaming(false);
          cb?.onDone?.();
          streamCallbacksRef.current = null;
          break;
        case 'error':
          setIsStreaming(false);
          cb?.onError?.(error || 'Unknown error');
          streamCallbacksRef.current = null;
          onErrorRef.current?.(error);
          break;
        case 'pong':
          break;
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;

      if (isClosingRef.current) return;

      const maxRetries = 5;
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);

      if (reconnectAttemptsRef.current < maxRetries) {
        reconnectAttemptsRef.current++;
        reconnectTimerRef.current = setTimeout(() => connect(), delay);
      }
    };

    ws.onerror = () => {};
  }, [testId, authToken, sessionId]);

  useEffect(() => {
    connect();
    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => {
      isClosingRef.current = true;
      clearInterval(pingInterval);
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const sendMessage = useCallback(({ message, currentFiles, onText, onDone, onError: onStreamError }) => {
    if (!message?.trim()) return;

    setIsStreaming(true);
    streamCallbacksRef.current = { onText, onDone, onError: onStreamError };

    const payload = JSON.stringify({
      type: 'message',
      message,
      currentFiles: currentFiles || {}
    });

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(payload);
    } else {
      pendingMessageRef.current = { type: 'message', message, currentFiles: currentFiles || {} };
      connect();
    }
  }, [connect]);

  return { sendMessage, isConnected, isStreaming };
}

export default useAIChat;