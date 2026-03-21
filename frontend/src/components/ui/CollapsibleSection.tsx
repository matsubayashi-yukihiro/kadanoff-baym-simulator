import { useState, type ReactNode } from "react";

export function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-border-soft rounded overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-ink-subtle bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        {title}
        <span className={`text-ink-muted text-xs transition-transform ${open ? "rotate-180" : ""}`}>
          &#9662;
        </span>
      </button>
      {open ? <div className="px-3 py-2.5 space-y-2.5">{children}</div> : null}
    </div>
  );
}
