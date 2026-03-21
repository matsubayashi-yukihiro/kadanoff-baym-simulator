import { useEffect, useRef, useState } from "react";

import { getRunProgress } from "../api/client";
import type { RunProgressRecord } from "../api/types";
import { toErrorMessage } from "../lib/helpers";

const POLL_INTERVAL_MS = 2000;
const STALE_MULTIPLIER = 2;

type UseRunProgressResult = {
  progress: RunProgressRecord | null;
  loading: boolean;
  error: string | null;
  isStale: boolean;
};

export function useRunProgress(runId: string | null, enabled: boolean): UseRunProgressResult {
  const [progress, setProgress] = useState<RunProgressRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (!runId || !enabled) {
      setProgress(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    const poll = async () => {
      setLoading((prev) => prev || progress === null);
      try {
        const next = await getRunProgress(runId);
        if (cancelled) return;
        setProgress(next);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(toErrorMessage(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [runId, enabled]);

  const isStale = progress != null
    && enabled
    && Date.now() - Date.parse(progress.updated_at) > POLL_INTERVAL_MS * STALE_MULTIPLIER;

  return { progress, loading, error, isStale };
}
