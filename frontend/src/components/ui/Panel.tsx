import type { ReactNode } from "react";

export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {children}
    </section>
  );
}

export function PanelHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="panel-header">
      <div>
        {eyebrow ? (
          <p className="eyebrow mb-1">{eyebrow}</p>
        ) : null}
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}
