import { useEffect, useMemo, useState } from "react";

import { getKSpaceNativeCatalog, getKSpaceNativeLesserSlice } from "../api/client";
import type {
  KSpaceNativeCatalogResponse,
  KSpaceNativeLesserSliceResponse,
  RunDetail,
} from "../api/types";
import { formatLabel, formatNumber } from "../lib/format";
import { clamp, isSuccessfulState, toErrorMessage } from "../lib/helpers";

type KSpaceNativePanelProps = {
  run: RunDetail | null;
};

export function KSpaceNativePanel(props: KSpaceNativePanelProps) {
  const { run } = props;
  const [catalog, setCatalog] = useState<KSpaceNativeCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [slice, setSlice] = useState<KSpaceNativeLesserSliceResponse | null>(null);
  const [sliceLoading, setSliceLoading] = useState(false);
  const [sliceError, setSliceError] = useState<string | null>(null);

  const [rowIndex, setRowIndex] = useState(0);
  const [colIndex, setColIndex] = useState(0);
  const [kIndex, setKIndex] = useState(0);
  const [nambuStart, setNambuStart] = useState(0);
  const [nambuWindow, setNambuWindow] = useState(2);

  const runId = run?.run_id ?? null;
  const isKSpace = run?.config?.representation === "k_space";
  const runCompleted = run ? isSuccessfulState(run.state) : false;

  useEffect(() => {
    setCatalog(null);
    setCatalogError(null);
    setSlice(null);
    setSliceError(null);
    setRowIndex(0);
    setColIndex(0);
    setKIndex(0);
    setNambuStart(0);
    setNambuWindow(2);
  }, [runId]);

  useEffect(() => {
    if (!runId || !isKSpace || !runCompleted) {
      return;
    }
    let cancelled = false;
    setCatalogLoading(true);
    getKSpaceNativeCatalog(runId)
      .then((result) => {
        if (cancelled) return;
        setCatalog(result);
        setCatalogError(null);
        setKIndex((current) => Math.min(current, Math.max(result.k_point_count - 1, 0)));
        setRowIndex((current) => Math.min(current, Math.max(result.time_point_count - 1, 0)));
        setColIndex((current) => Math.min(current, Math.max(result.time_point_count - 1, 0)));
        setNambuStart((current) => Math.min(current, Math.max(result.nambu_dimension - 1, 0)));
        setNambuWindow((current) => clamp(current, 1, Math.max(result.nambu_dimension, 1)));
      })
      .catch((error) => {
        if (cancelled) return;
        setCatalog(null);
        setCatalogError(toErrorMessage(error));
      })
      .finally(() => {
        if (!cancelled) {
          setCatalogLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [runId, isKSpace, runCompleted]);

  useEffect(() => {
    if (!runId || !catalog) {
      return;
    }
    const rowStop = clamp(rowIndex + 1, 1, catalog.time_point_count);
    const colStop = clamp(colIndex + 1, 1, catalog.time_point_count);
    const kStop = clamp(kIndex + 1, 1, catalog.k_point_count);
    const nambuStop = clamp(nambuStart + nambuWindow, 1, catalog.nambu_dimension);

    let cancelled = false;
    setSliceLoading(true);
    getKSpaceNativeLesserSlice(runId, {
      row_start: Math.min(rowIndex, rowStop - 1),
      row_stop: rowStop,
      col_start: Math.min(colIndex, colStop - 1),
      col_stop: colStop,
      k_start: Math.min(kIndex, kStop - 1),
      k_stop: kStop,
      nambu_start: Math.min(nambuStart, nambuStop - 1),
      nambu_stop: nambuStop,
    })
      .then((result) => {
        if (cancelled) return;
        setSlice(result);
        setSliceError(null);
      })
      .catch((error) => {
        if (cancelled) return;
        setSlice(null);
        setSliceError(toErrorMessage(error));
      })
      .finally(() => {
        if (!cancelled) {
          setSliceLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId, catalog, rowIndex, colIndex, kIndex, nambuStart, nambuWindow]);

  const selectedPoint = useMemo(
    () => catalog?.points[kIndex] ?? null,
    [catalog, kIndex],
  );

  const maxTimeIndex = Math.max((catalog?.time_point_count ?? 1) - 1, 0);
  const maxKIndex = Math.max((catalog?.k_point_count ?? 1) - 1, 0);
  const maxNambuIndex = Math.max((catalog?.nambu_dimension ?? 1) - 1, 0);
  const maxWindow = Math.max(catalog?.nambu_dimension ?? 1, 1);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Contour</p>
          <h2>K-Space Native Lesser Slice</h2>
        </div>
        {run ? <span className={`status-pill status-${run.state}`}>{run.state}</span> : null}
      </div>

      {!run ? (
        <div className="empty-card">
          <p>No run selected.</p>
          <p>Select a `k_space` run to inspect 2x2 k-block trajectories.</p>
        </div>
      ) : null}

      {run && !isKSpace ? (
        <div className="empty-card">
          <p>This panel is available only for `representation=k_space` runs.</p>
        </div>
      ) : null}

      {run && isKSpace && !runCompleted ? (
        <p className="state-banner">k-space native slices unlock after run completion.</p>
      ) : null}

      {catalogLoading ? <p className="state-banner">Loading k-space native catalog...</p> : null}
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
              <span className="focus-key">k Points</span>
              <span>{catalog.k_point_count}</span>
            </div>
            <div>
              <span className="focus-key">Reconstruction</span>
              <span>{catalog.reconstruction_mode ?? "n/a"}</span>
            </div>
          </div>

          <div className="panel-grid panel-grid-2">
            <NumericField label="Row Index" value={rowIndex} min={0} max={maxTimeIndex} onChange={setRowIndex} />
            <NumericField label="Column Index" value={colIndex} min={0} max={maxTimeIndex} onChange={setColIndex} />
          </div>
          <div className="panel-grid panel-grid-2">
            <NumericField label="k Index" value={kIndex} min={0} max={maxKIndex} onChange={setKIndex} />
            <NumericField label="Nambu Start" value={nambuStart} min={0} max={maxNambuIndex} onChange={setNambuStart} />
          </div>
          <div className="panel-grid panel-grid-2">
            <NumericField label="Nambu Window" value={nambuWindow} min={1} max={maxWindow} onChange={setNambuWindow} />
            <div className="metric-card">
              <span className="metric-label">Selected k</span>
              <span className="metric-value">
                {selectedPoint
                  ? `${selectedPoint.index} (${selectedPoint.grid_index_x}, ${selectedPoint.grid_index_y})`
                  : "n/a"}
              </span>
            </div>
          </div>

          {selectedPoint ? (
            <p className="hint-text">
              {formatLabel("kx")}: {formatNumber(selectedPoint.kx, 4)}, {formatLabel("ky")}: {formatNumber(selectedPoint.ky, 4)}
            </p>
          ) : null}
        </>
      ) : null}

      {sliceLoading ? <p className="state-banner">Loading k-space native lesser slice...</p> : null}
      {sliceError ? <p className="state-banner state-error">{sliceError}</p> : null}

      {slice ? (
        <div className="green-function-body">
          <div className="observable-meta">
            <div>
              <span className="focus-key">Component</span>
              <span>{slice.component}</span>
            </div>
            <div>
              <span className="focus-key">Row Time</span>
              <span>{formatNumber(slice.times_row[0] ?? 0, 4)}</span>
            </div>
            <div>
              <span className="focus-key">Column Time</span>
              <span>{formatNumber(slice.times_col[0] ?? 0, 4)}</span>
            </div>
            <div>
              <span className="focus-key">Slice Shape</span>
              <span>{slice.shape.join(" x ")}</span>
            </div>
          </div>
          <div className="green-matrix-grid">
            <MatrixCard title="Re" values={slice.real[0]?.[0]?.[0] ?? []} />
            <MatrixCard title="Im" values={slice.imag[0]?.[0]?.[0] ?? []} />
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
