import type { ReactNode } from "react";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink-subtle">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-ink-muted mt-0.5">{hint}</span> : null}
    </label>
  );
}
