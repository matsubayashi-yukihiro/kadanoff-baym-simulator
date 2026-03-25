import type { GreenFunctionCatalogResponse, GreenFunctionSliceResponse, RunDetail } from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";
import { isSuccessfulState } from "../lib/helpers";

type GreenFunctionPanelProps = {
  run: RunDetail | null;
  catalog: GreenFunctionCatalogResponse | null;
  catalogLoading: boolean;
  catalogError: string | null;
  selectedComponent: string | null;
  onSelectComponent: (component: string) => void;
  rowIndex: number;
  colIndex: number;
  nambuStart: number;
  nambuWindow: number;
  onRowIndexChange: (value: number) => void;
  onColIndexChange: (value: number) => void;
  onNambuStartChange: (value: number) => void;
  onNambuWindowChange: (value: number) => void;
  slice: GreenFunctionSliceResponse | null;
  sliceLoading: boolean;
  sliceError: string | null;
};

export function GreenFunctionPanel(props: GreenFunctionPanelProps) {
  const {
    run,
    catalog,
    catalogLoading,
    catalogError,
    selectedComponent,
    onSelectComponent,
    rowIndex,
    colIndex,
    nambuStart,
    nambuWindow,
    onRowIndexChange,
    onColIndexChange,
    onNambuStartChange,
    onNambuWindowChange,
    slice,
    sliceLoading,
    sliceError,
  } = props;

  const isKbeRun = run?.solver === "kbe_hfb";
  const runCompleted = run ? isSuccessfulState(run.state) : false;
  const maxTimeIndex = Math.max((catalog?.time_point_count ?? 1) - 1, 0);
  const maxNambuIndex = Math.max((catalog?.nambu_dimension ?? 1) - 1, 0);
  const maxWindow = Math.max(catalog?.nambu_dimension ?? 1, 1);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Contour</p>
          <h2>Green Function Slice</h2>
        </div>
        {run ? <span className={`status-pill status-${run.state}`}>{run.state}</span> : null}
      </div>

      {!run ? (
        <div className="empty-card">
          <p>No KBE run selected.</p>
          <p>Choose a completed `kbe_hfb` run to inspect two-time slices.</p>
        </div>
      ) : null}

      {run && !isKbeRun ? (
        <div className="empty-card">
          <p>Green-function inspection is only available for `kbe_hfb` runs.</p>
          <p>This panel unlocks when two-time retarded and lesser data are stored.</p>
        </div>
      ) : null}

      {run && isKbeRun && !runCompleted ? (
        <p className="state-banner">
          Green-function slices will unlock after the run completes (`succeeded` or `succeeded_with_warnings`).
        </p>
      ) : null}

      {run && isKbeRun && runCompleted && catalogLoading ? (
        <p className="state-banner">Loading green-function catalog...</p>
      ) : null}
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
              <span className="focus-key">Shape</span>
              <span>{catalog.shape.join(" x ")}</span>
            </div>
            <div>
              <span className="focus-key">Nambu Dimension</span>
              <span>{catalog.nambu_dimension}</span>
            </div>
          </div>

          <div className="chip-row" role="tablist" aria-label="Green function component selector">
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

          <div className="panel-grid panel-grid-3">
            <NumericField
              label="Row Index"
              value={rowIndex}
              min={0}
              max={maxTimeIndex}
              onChange={onRowIndexChange}
            />
            <NumericField
              label="Column Index"
              value={colIndex}
              min={0}
              max={maxTimeIndex}
              onChange={onColIndexChange}
            />
            <NumericField
              label="Nambu Start"
              value={nambuStart}
              min={0}
              max={maxNambuIndex}
              onChange={onNambuStartChange}
            />
          </div>

          <div className="panel-grid">
            <NumericField
              label="Nambu Window"
              value={nambuWindow}
              min={1}
              max={maxWindow}
              onChange={onNambuWindowChange}
            />
            <div className="metric-card">
              <span className="metric-label">Requested Block</span>
              <span className="metric-value">
                {nambuStart}:{nambuStart + nambuWindow}
              </span>
            </div>
          </div>
        </>
      ) : null}

      {sliceLoading ? <p className="state-banner">Loading green-function slice...</p> : null}
      {sliceError ? <p className="state-banner state-error">{sliceError}</p> : null}

      {slice ? (
        <div className="green-function-body">
          <div className="observable-meta">
            <div>
              <span className="focus-key">Component</span>
              <span>{formatLabel(slice.component)}</span>
            </div>
            <div>
              <span className="focus-key">Row Time</span>
              <span>{formatNumber(slice.times_row[0] ?? "-", 4)}</span>
            </div>
            <div>
              <span className="focus-key">Column Time</span>
              <span>{formatNumber(slice.times_col[0] ?? "-", 4)}</span>
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
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}
