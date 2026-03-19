import { useCallback, useEffect, useState } from "react";

import { getRunLog } from "../api/client";
import type { RunDetail } from "../api/types";
import { isTerminalState, toErrorMessage } from "../lib/helpers";

interface Props {
  run: RunDetail | null;
}

export function RunLogPanel({ run }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [log, setLog] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runId = run?.run_id ?? null;
  const showable = run != null && isTerminalState(run.state);

  const fetchLog = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const text = await getRunLog(id);
      setLog(text);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLog(null);
    setError(null);
    setExpanded(false);
  }, [runId]);

  useEffect(() => {
    if (expanded && log === null && !loading && runId) {
      fetchLog(runId);
    }
  }, [expanded, log, loading, runId, fetchLog]);

  if (!showable) return null;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Solver Output</p>
          <h2>Run Log</h2>
        </div>
      </div>
      <button
        type="button"
        className="log-viewer-toggle"
        onClick={() => setExpanded((prev) => !prev)}
      >
        {expanded ? "▾ Hide log" : "▸ Show log"}
      </button>
      {expanded && (
        <div className="log-viewer">
          {loading && <p className="hint-text">Loading…</p>}
          {error && <p className="state-banner state-error">{error}</p>}
          {log !== null && !loading && (
            <pre>{log || "(empty log)"}</pre>
          )}
        </div>
      )}
    </section>
  );
}
