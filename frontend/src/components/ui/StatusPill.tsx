const STATE_STYLES: Record<string, string> = {
  queued: "bg-queued/10 text-queued",
  running: "bg-accent-secondary/10 text-accent-secondary",
  succeeded: "bg-success/10 text-success",
  succeeded_with_warnings: "bg-success/10 text-success border border-queued/40",
  failed: "bg-danger/10 text-danger",
  cancelled: "bg-ink-muted/10 text-ink-muted",
};

export function StatusPill({ state }: { state: string }) {
  return (
    <span
      className={`px-3 py-1 rounded-full text-xs font-medium ${STATE_STYLES[state] ?? STATE_STYLES.cancelled}`}
    >
      {state}
    </span>
  );
}
