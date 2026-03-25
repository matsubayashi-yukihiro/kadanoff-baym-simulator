import type { MixedGreenFunctionCatalogResponse, MixedGreenFunctionSliceResponse, RunDetail } from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";
import { isSuccessfulState } from "../lib/helpers";

type MixedGreenFunctionPanelProps = {
  run: RunDetail | null;
  catalog: MixedGreenFunctionCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedComponent: string | null;
  onSelectComponent: (component: string) => void;
  timeIndex: number;
  tauIndex: number;
  nambuStart: number;
  nambuWindow: number;
  onTimeIndexChange: (value: number) => void;
  onTauIndexChange: (value: number) => void;
  onNambuStartChange: (value: number) => void;
  onNambuWindowChange: (value: number) => void;
  slice: MixedGreenFunctionSliceResponse | null;
  sliceLoading: boolean;
  sliceError: string | null;
};

export function MixedGreenFunctionPanel(props: MixedGreenFunctionPanelProps) {
  const {
    run,
    catalog,
    catalogLoading,
    catalogError,
    selectedComponent,
    onSelectComponent,
    timeIndex,
    tauIndex,
    nambuStart,
    nambuWindow,
    onTimeIndexChange,
    onTauIndexChange,
    onNambuStartChange,
    onNambuWindowChange,
    slice,
    sliceLoading,
    sliceError,
  } = props;

  const isKbeRun = run?.solver === "kbe_hfb";
  const thermalEnabled = run?.config?.thermal_branch?.enabled === true;
  const runCompleted = run ? isSuccessfulState(run.state) : false;
  const maxTimeIndex = Math.max((catalog?.time_point_count ?? 1) - 1, 0);
  const maxTauIndex = Math.max((catalog?.tau_point_count ?? 1) - 1, 0);
  const maxNambuIndex = Math.max((catalog?.nambu_dimension ?? 1) - 1, 0);
  const maxWindow = Math.max(catalog?.nambu_dimension ?? 1, 1);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Contour</p>
          <h2>Mixed Green Function</h2>
        </div>
        {run ? <span className={`status-pill status-${run.state}`}>{run.state}</span> : null}
      </div>

      {!run ? (
        <div className="empty-card">
          <p>No KBE run selected.</p>
          <p>Choose a completed `kbe_hfb` run with thermal branch enabled to inspect mixed contour slices.</p>
        </div>
      ) : null}

      {run && !isKbeRun ? (
        <div className="empty-card">
          <p>Mixed Green function inspection is only available for `kbe_hfb` runs.</p>
        </div>
      ) : null}

      {run && isKbeRun && !thermalEnabled ? (
        <div className="empty-card">
          <p>Mixed Green functions require the thermal branch to be enabled.</p>
          <p>Enable `thermal_branch.enabled` in the config to store mixed contour data.</p>
        </div>
      ) : null}

      {run && isKbeRun && thermalEnabled && !runCompleted ? (
        <p className="state-banner">
          Mixed Green-function slices will unlock after the run completes (`succeeded` or `succeeded_with_warnings`).
        </p>
      ) : null}

      {catalogLoading ? <p className="state-banner">Loading mixed Green function catalog...</p> : null}
      {catalogError ? <p className="state-banner state-error">{catalogError}</p> : null}

      {catalog ? (
        <>
          <div className="diagnostic-summary">
            <div>
              <span className="focus-key">Components</span>
              <span>{catalog.components.join(", ")}</span>
            </div>
            <div>
              <span className="focus-key">Time Points</span>
              <span>{catalog.time_point_count}</span>
            </div>
            <div>
              <span className="focus-key">Tau Points</span>
              <span>{catalog.tau_point_count}</span>
            </div>
            <div>
              <span className="focus-key">Shape</span>
              <span>{catalog.shape.join(" x ")}</span>
            </div>
            <div>
              <span className="focus-key">Nambu Dimension</span>
              <span>{catalog.nambu_dimension}</span>
            </div>
          </div>

          <div className="chip-row" role="tablist" aria-label="Mixed Green function component selector">
            {catalog.components.map((component) => (
              <button
                key={component}
                type="button"
                className={`chip ${selectedComponent === component ? "chip-active" : ""}`}
                onClick={() => onSelectComponent(component)}
              >
                {formatLabel(component)}
              </button>
            ))}
          </div>

          <div className="panel-grid panel-grid-2">
            <NumericField label="Time Index" value={timeIndex} min={0} max={maxTimeIndex} onChange={onTimeIndexChange} />
            <NumericField label="Tau Index" value={tauIndex} min={0} max={maxTauIndex} onChange={onTauIndexChange} />
          </div>
          <div className="panel-grid panel-grid-2">
            <NumericField label="Nambu Start" value={nambuStart} min={0} max={maxNambuIndex} onChange={onNambuStartChange} />
            <NumericField label="Nambu Window" value={nambuWindow} min={1} max={maxWindow} onChange={onNambuWindowChange} />
          </div>
        </>
      ) : null}

      {sliceLoading ? <p className="state-banner">Loading mixed Green function slice...</p> : null}
      {sliceError ? <p className="state-banner state-error">{sliceError}</p> : null}

      {slice ? (
        <div className="green-function-body">
          <div className="observable-meta">
            <div>
              <span className="focus-key">Component</span>
              <span>{formatLabel(slice.component)}</span>
            </div>
            <div>
              <span className="focus-key">Time</span>
              <span>{formatNumber(slice.times[0] ?? "-", 4)}</span>
            </div>
            <div>
              <span className="focus-key">Tau</span>
              <span>{formatNumber(slice.tau[0] ?? "-", 4)}</span>
            </div>
            <div>
              <span className="focus-key">Slice Shape</span>
              <span>{slice.shape.join(" x ")}</span>
            </div>
          </div>

          <div className="green-matrix-grid">
            <MatrixCard title="Re" values={slice.real[0]?.[0] ?? []} />
            <MatrixCard title="Im" values={slice.imag[0]?.[0] ?? []} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

type NumericFieldProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
};

function NumericField(props: NumericFieldProps) {
  const { label, value, min, max, onChange } = props;
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input
        aria-label={label}
        type="number"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(event) => onChange(clampInteger(event.target.value, value, min, max))}
      />
    </label>
  );
}

type MatrixCardProps = {
  title: string;
  values: number[][];
};

function MatrixCard(props: MatrixCardProps) {
  const { title, values } = props;
  return (
    <div className="green-matrix-card">
      <div className="panel-subheader">
        <h3>{title}</h3>
      </div>
      {values.length === 0 ? (
        <div className="empty-card">
          <p>No matrix entries loaded.</p>
        </div>
      ) : (
        <div className="matrix-scroll">
          <table className="matrix-table">
            <tbody>
              {values.map((row, rowIndex) => (
                <tr key={`${title}-row-${rowIndex}`}>
                  {row.map((value, columnIndex) => (
                    <td key={`${title}-${rowIndex}-${columnIndex}`}>{formatNumber(value, 4)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function clampInteger(rawValue: string, fallback: number, min: number, max: number): number {
  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}
