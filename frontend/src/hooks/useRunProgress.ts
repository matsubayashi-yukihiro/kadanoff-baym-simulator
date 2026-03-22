import { useEffect, useRef, useState } from "react";

import { getRunProgress } from "../api/client";
import type { RunProgressRecord } from "../api/types";
import { toErrorMessage } from "../lib/helpers";

const POLL_INTERVAL_MS = 2000;
const NETWORK_STALE_MS = POLL_INTERVAL_MS * 3;
const PROGRESS_STALE_MS = Math.max(POLL_INTERVAL_MS * 15, 30000);

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
  const [clockMs, setClockMs] = useState(() => Date.now());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSuccessfulPollAtRef = useRef<number | null>(null);
  const lastProgressSignatureRef = useRef<string | null>(null);
  const lastProgressChangeAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (!runId || !enabled) {
      setProgress(null);
      setError(null);
      setLoading(false);
      setClockMs(Date.now());
      lastSuccessfulPollAtRef.current = null;
      lastProgressSignatureRef.current = null;
      lastProgressChangeAtRef.current = null;
      return;
    }

    let cancelled = false;

    const poll = async () => {
      setLoading((prev) => prev || progress === null);
      try {
        const next = await getRunProgress(runId);
        if (cancelled) return;
        const now = Date.now();
        const signature = buildProgressSignature(next);
        if (signature !== lastProgressSignatureRef.current) {
          lastProgressSignatureRef.current = signature;
          lastProgressChangeAtRef.current = now;
        }
        lastSuccessfulPollAtRef.current = now;
        setProgress(next);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(toErrorMessage(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
          setClockMs(Date.now());
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

  const now = clockMs;
  const noRecentSuccessfulPoll = progress != null
    && enabled
    && lastSuccessfulPollAtRef.current != null
    && now - lastSuccessfulPollAtRef.current > NETWORK_STALE_MS;
  const noRecentProgressChange = progress != null
    && enabled
    && progress.state === "running"
    && lastProgressChangeAtRef.current != null
    && now - lastProgressChangeAtRef.current > PROGRESS_STALE_MS;
  const isStale = noRecentSuccessfulPoll || noRecentProgressChange;

  return { progress, loading, error, isStale };
}

function buildProgressSignature(progress: RunProgressRecord): string {
  return [
    progress.phase,
    progress.state,
    progress.updated_at,
    progress.accepted_steps,
    progress.rejected_steps,
    progress.saved_samples_written,
    progress.physical_progress_fraction,
    progress.status_line ?? "",
  ].join("|");
}
