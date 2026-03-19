import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Single Job", end: true },
  { to: "/compare-jobs", label: "Compare Jobs" },
  { to: "/parameter-sweep", label: "Parameter Sweep" },
] as const;

export function NavTabs() {
  return (
    <nav className="px-6 flex gap-1 border-b border-border-soft" aria-label="Workbench navigation">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === "/" ? true : undefined}
          className={({ isActive }) =>
            `px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              isActive
                ? "bg-panel text-ink border border-b-0 border-panel-border -mb-px"
                : "text-ink-muted hover:text-ink hover:bg-panel-strong/50"
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
