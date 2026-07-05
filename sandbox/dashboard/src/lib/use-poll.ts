"use client";

import { useEffect, useRef, useState } from "react";

export interface PollState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  lastUpdated: number | null;
}

// usePoll runs an async fetcher on an interval and tracks state. The fetcher is
// held in a ref so the interval is stable and not torn down each render.
export function usePoll<T>(fetcher: () => Promise<T>, intervalMs = 3000): PollState<T> {
  const [state, setState] = useState<PollState<T>>({
    data: null,
    error: null,
    loading: true,
    lastUpdated: null,
  });
  const fn = useRef(fetcher);
  fn.current = fetcher;

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const data = await fn.current();
        if (alive) setState({ data, error: null, loading: false, lastUpdated: Date.now() });
      } catch (e) {
        if (alive) setState((s) => ({ ...s, error: String((e as Error).message || e), loading: false }));
      }
    };
    tick();
    const h = setInterval(tick, intervalMs);
    return () => {
      alive = false;
      clearInterval(h);
    };
  }, [intervalMs]);

  return state;
}
