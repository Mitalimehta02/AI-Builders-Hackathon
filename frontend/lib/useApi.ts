"use client";

// Loads data from the backend with loading and error state, an optional refresh interval, and a
// reload() for "Try again" buttons. `key` identifies the request: when it changes, data is reloaded.

import { useCallback, useEffect, useRef, useState } from "react";

type State<T> = { data: T | null; error: Error | null; loading: boolean };

export function useApi<T>(key: string, fetcher: () => Promise<T>, refreshMs?: number) {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let cancelled = false;
    const run = () =>
      fetcherRef.current()
        .then((data) => { if (!cancelled) setState({ data, error: null, loading: false }); })
        .catch((error: Error) => { if (!cancelled) setState((previous) => ({ data: previous.data, error, loading: false })); });
    run();
    const timer = refreshMs ? setInterval(run, refreshMs) : undefined;
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [key, attempt, refreshMs]);

  const reload = useCallback(() => {
    setState((previous) => ({ ...previous, loading: true }));
    setAttempt((count) => count + 1);
  }, []);

  return { ...state, reload };
}
