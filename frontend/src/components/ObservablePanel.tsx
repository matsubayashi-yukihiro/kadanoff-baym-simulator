import type { ObservableCatalogResponse, ObservableResponse, RunDetail } from "../api/types";
import { formatLabel } from "../lib/format";
import { LineChart } from "./LineChart";

type ObservablePanelProps = {
  catalog: ObservableCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  data: ObservableResponse | null;
  dataLoading: boolean;
  dataError: string | null;
  run: RunDetail | null;
  selectedObservable: string | null;
  onSelectObservable: (name: string) => void;
};

export function ObservablePanel(props: ObservablePanelProps) {
  const { catalog, catalogLoading, catalogError, data, dataLoading, dataError, run, selectedObservable, onSelectObservable } =
    props;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Observables</p>
          <h2>ObservablePanel</h2>
        </div>
        {run ? <span className={`status-pill status-${run.state}`}>{run.state}</span> : null}
      </div>

      {!run ? (
        <div className="empty-card">
          <p>No observable source selected.</p>
          <p>Choose a run to inspect time series.</p>
        </div>
      ) : null}

      {run && run.state !== "succeeded" ? (
        <p className="state-banner">Observables will unlock after the run reaches `succeeded`.</p>
      ) : null}
      {catalogLoading ? <p className="state-banner">Loading observable catalog...</p> : null}
      {catalogError ? <p className="state-banner state-error">{catalogError}</p> : null}

      {catalog && catalog.observables.length > 0 ? (
        <div className="chip-row" role="tablist" aria-label="Observable selector">
          {catalog.observables.map((name) => (
            <button
              key={name}
              type="button"
              className={`chip ${selectedObservable === name ? "chip-active" : ""}`}
              onClick={() => onSelectObservable(name)}
            >
              {formatLabel(name)}
            </button>
          ))}
        </div>
      ) : null}

      {run && run.state === "succeeded" && catalog && catalog.observables.length === 0 ? (
        <div className="empty-card">
          <p>No observables were saved for this run.</p>
          <p>Adjust the observable list in the config and resubmit.</p>
        </div>
      ) : null}

      {dataLoading ? <p className="state-banner">Loading time series...</p> : null}
      {dataError ? <p className="state-banner state-error">{dataError}</p> : null}

      {data ? (
        <div className="observable-body">
          <div className="observable-meta">
            <div>
              <span className="focus-key">Observable</span>
              <span>{formatLabel(data.name)}</span>
            </div>
            <div>
              <span className="focus-key">Samples</span>
              <span>{data.time.length}</span>
            </div>
            <div>
              <span className="focus-key">Series</span>
              <span>{data.series.length}</span>
            </div>
          </div>
          <LineChart data={data} />
        </div>
      ) : null}
    </section>
  );
}
