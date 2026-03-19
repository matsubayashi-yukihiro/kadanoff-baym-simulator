import type { ReactNode } from "react";

export function Sidebar({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  return (
    <aside className="w-80 shrink-0 flex flex-col border-r border-border-soft h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {children}
      </div>
      {footer ? (
        <div className="sticky bottom-0 p-4 border-t border-border-soft bg-panel-strong/95 backdrop-blur-sm">
          {footer}
        </div>
      ) : null}
    </aside>
  );
}
