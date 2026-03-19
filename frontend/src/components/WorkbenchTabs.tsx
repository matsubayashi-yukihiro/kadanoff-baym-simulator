import type { WorkbenchTab } from "../lib/workbench";
import { WORKBENCH_TABS } from "../lib/workbench";

type WorkbenchTabsProps = {
  activeTab: WorkbenchTab;
  onSelectTab: (tab: WorkbenchTab) => void;
};

export function WorkbenchTabs(props: WorkbenchTabsProps) {
  const { activeTab, onSelectTab } = props;

  return (
    <section className="tabs-shell" aria-label="Workbench navigation">
      <div className="tabs-header">
        <div>
          <p className="eyebrow">Workbench Pages</p>
          <h2>Research Surfaces</h2>
        </div>
        <p className="tabs-copy">Keep single-run inspection, comparison design, and sweep planning on separate pages.</p>
      </div>

      <nav className="tabs-row" aria-label="Top-level workbench pages">
        {WORKBENCH_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            aria-current={activeTab === tab.key ? "page" : undefined}
            className={`tab-button ${activeTab === tab.key ? "tab-button-active" : ""}`}
            onClick={() => onSelectTab(tab.key)}
          >
            <span className="tab-label">{tab.label}</span>
            <span className="tab-description">{tab.description}</span>
          </button>
        ))}
      </nav>
    </section>
  );
}
