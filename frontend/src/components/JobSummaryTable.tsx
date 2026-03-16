import { Fragment, useEffect, useState } from "react";

import type { RunDetail } from "../api/types";
import {
  columnValueDiffers,
  shortRunId,
  type JobColumn,
  type WorkspaceJob,
} from "../lib/workspace";
import { EditableCell } from "./EditableCell";

const TITLE_COLUMN: JobColumn = {
  id: "job_title",
  label: "Job Name",
  kind: "text",
};

type JobSummaryTableProps = {
  jobs: WorkspaceJob[];
  activeJobId: string | null;
  runsById: Record<string, RunDetail>;
  parameterColumns: JobColumn[];
  showDifferentOnly: boolean;
  onToggleShowDifferentOnly: (value: boolean) => void;
  onSelectJob: (jobId: string) => void;
  onUpdateJobTitle: (jobId: string, title: string) => void;
  onUpdateJobParameter: (jobId: string, column: JobColumn, value: unknown) => void;
  onTogglePlot: (jobId: string, enabled: boolean) => void;
  onDuplicateJob: (jobId: string) => void;
  onDeleteJob: (jobId: string) => void;
};

type ColumnPage = {
  id: string;
  label: string;
  columns: JobColumn[];
};

const COLUMN_PAGE_GROUPS: Array<{ id: string; label: string; prefixes: string[] }> = [
  {
    id: "core",
    label: "Core",
    prefixes: ["solver", "lattice", "time"],
  },
  {
    id: "field",
    label: "Field+State",
    prefixes: ["drive", "interaction", "initial_state"],
  },
  {
    id: "advanced",
    label: "Advanced",
    prefixes: ["kbe", "adaptive", "thermal_branch"],
  },
];

export function JobSummaryTable(props: JobSummaryTableProps) {
  const {
    jobs,
    activeJobId,
    runsById,
    parameterColumns,
    showDifferentOnly,
    onToggleShowDifferentOnly,
    onSelectJob,
    onUpdateJobTitle,
    onUpdateJobParameter,
    onTogglePlot,
    onDuplicateJob,
    onDeleteJob,
  } = props;

  const columnPages = buildColumnPages(parameterColumns);
  const [pageIndex, setPageIndex] = useState(0);
  const activePage = columnPages[pageIndex] ?? null;
  const [upperColumns, lowerColumns] = splitColumns(activePage?.columns ?? []);
  const baselineJob = jobs.find((job) => job.id === activeJobId) ?? jobs[0] ?? null;

  useEffect(() => {
    if (columnPages.length === 0) {
      if (pageIndex !== 0) {
        setPageIndex(0);
      }
      return;
    }

    if (pageIndex > columnPages.length - 1) {
      setPageIndex(columnPages.length - 1);
    }
  }, [columnPages.length, pageIndex]);

  return (
    <section className="panel summary-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Job Matrix</p>
          <h2>Editable DataFrame</h2>
        </div>
        <label className="toggle-pill">
          <input
            type="checkbox"
            checked={showDifferentOnly}
            onChange={(event) => onToggleShowDifferentOnly(event.target.checked)}
          />
          <span>Only differing fields</span>
        </label>
      </div>

      <div className="matrix-toolbar">
        <div className="matrix-page-controls">
          <button
            type="button"
            className="ghost-button row-action-button"
            onClick={() => setPageIndex((current) => Math.max(current - 1, 0))}
            disabled={pageIndex === 0}
          >
            Prev
          </button>
          {columnPages.map((page, index) => (
            <button
              key={page.id}
              type="button"
              className={`chip ${index === pageIndex ? "chip-active" : ""}`}
              onClick={() => setPageIndex(index)}
            >
              {page.label} <span className="matrix-chip-count">{page.columns.length}</span>
            </button>
          ))}
          <button
            type="button"
            className="ghost-button row-action-button"
            onClick={() => setPageIndex((current) => Math.min(current + 1, Math.max(columnPages.length - 1, 0)))}
            disabled={pageIndex >= columnPages.length - 1}
          >
            Next
          </button>
        </div>
        <span className="state-inline">
          Page {columnPages.length === 0 ? 0 : pageIndex + 1}/{columnPages.length}
        </span>
      </div>

      <p className="summary-note">
        Dense spreadsheet view. Jobs stay on rows, and related parameter blocks are bundled into a few wide pages
        instead of many narrow ones.
      </p>

      <div className="dataframe-shell">
        <table className="dataframe-table">
          <thead>
            <tr>
              <th className="dataframe-meta-head" rowSpan={2}>
                Job
              </th>
              <th className="dataframe-meta-head" rowSpan={2}>
                Run
              </th>
              <th className="dataframe-meta-head" rowSpan={2}>
                Actions
              </th>
              {upperColumns.map((column) => (
                <th key={column.id} className="dataframe-parameter-head">
                  <span>{column.label}</span>
                  <small>{column.id}</small>
                </th>
              ))}
            </tr>
            <tr>
              {lowerColumns.map((column) => (
                <th key={column.id} className="dataframe-parameter-head">
                  <span>{column.label}</span>
                  <small>{column.id}</small>
                </th>
              ))}
              {Array.from({ length: Math.max(upperColumns.length - lowerColumns.length, 0) }, (_, index) => (
                <th key={`header-placeholder-${index}`} className="dataframe-placeholder-head" aria-hidden="true" />
              ))}
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => {
              const run = job.lastRunId ? runsById[job.lastRunId] : undefined;
              return (
                <Fragment key={job.id}>
                  <tr
                    data-testid={`job-row-${job.id}`}
                    className={job.id === activeJobId ? "dataframe-row-active" : ""}
                    onClick={() => onSelectJob(job.id)}
                  >
                    <td className="dataframe-job-cell" rowSpan={2}>
                      <div className="dataframe-job-stack">
                        <EditableCell
                          jobLabel={job.title}
                          column={TITLE_COLUMN}
                          value={job.title}
                          onCommit={(value) => onUpdateJobTitle(job.id, String(value ?? ""))}
                        />
                        <div className="dataframe-job-meta">
                          <span className={`status-pill status-${run?.state ?? "queued"}`}>{run?.state ?? "draft"}</span>
                          <label className="dataframe-plot-toggle">
                            <input
                              aria-label={`${job.title} plot`}
                              className="cell-checkbox"
                              type="checkbox"
                              checked={job.plotEnabled}
                              onChange={(event) => onTogglePlot(job.id, event.target.checked)}
                            />
                            <span>plot</span>
                          </label>
                        </div>
                      </div>
                    </td>

                    <td className="dataframe-readonly" rowSpan={2}>
                      <div>{shortRunId(job.lastRunId)}</div>
                      {run?.updated_at ? <small>{new Date(run.updated_at).toLocaleTimeString()}</small> : <small>-</small>}
                    </td>

                    <td onClick={(event) => event.stopPropagation()} rowSpan={2}>
                      <div className="dataframe-action-row">
                        <button
                          type="button"
                          className="ghost-button row-action-button"
                          aria-label={`${job.title} duplicate`}
                          onClick={() => onDuplicateJob(job.id)}
                        >
                          Dup
                        </button>
                        <button
                          type="button"
                          className="ghost-button row-action-button"
                          aria-label={`${job.title} delete`}
                          onClick={() => onDeleteJob(job.id)}
                        >
                          Del
                        </button>
                      </div>
                    </td>

                    {upperColumns.map((column) => renderParameterCell(job, column, baselineJob, onUpdateJobParameter))}
                  </tr>
                  <tr
                    className={`${job.id === activeJobId ? "dataframe-row-active" : ""} dataframe-row-secondary`}
                    onClick={() => onSelectJob(job.id)}
                  >
                    {lowerColumns.map((column) => renderParameterCell(job, column, baselineJob, onUpdateJobParameter))}
                    {Array.from({ length: Math.max(upperColumns.length - lowerColumns.length, 0) }, (_, index) => (
                      <td key={`${job.id}-placeholder-${index}`} className="dataframe-cell-placeholder" aria-hidden="true" />
                    ))}
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function buildColumnPages(columns: JobColumn[]): ColumnPage[] {
  const pages = COLUMN_PAGE_GROUPS.map((group) => ({
    id: group.id,
    label: group.label,
    columns: columns.filter((column) => group.prefixes.includes(column.path?.split(".")[0] ?? "general")),
  })).filter((page) => page.columns.length > 0);

  const assignedPrefixes = new Set(COLUMN_PAGE_GROUPS.flatMap((group) => group.prefixes));
  const overflowColumns = columns.filter((column) => !assignedPrefixes.has(column.path?.split(".")[0] ?? "general"));

  if (overflowColumns.length > 0) {
    pages.push({
      id: "other",
      label: "Other",
      columns: overflowColumns,
    });
  }

  return pages;
}

function splitColumns(columns: JobColumn[]): [JobColumn[], JobColumn[]] {
  const midpoint = Math.ceil(columns.length / 2);
  return [columns.slice(0, midpoint), columns.slice(midpoint)];
}

function renderParameterCell(
  job: WorkspaceJob,
  column: JobColumn,
  baselineJob: WorkspaceJob | null,
  onUpdateJobParameter: (jobId: string, column: JobColumn, value: unknown) => void,
) {
  const value = column.path ? getValue(job, column.path) : null;
  const differs = columnValueDiffers(column, job, baselineJob);

  return (
    <td
      key={`${job.id}-${column.id}`}
      data-testid={`cell-${job.id}-${column.id}`}
      className={differs ? "dataframe-cell-diff" : ""}
    >
      <EditableCell
        jobLabel={`${job.title} ${column.label}`}
        column={column}
        value={value}
        onCommit={(nextValue) => onUpdateJobParameter(job.id, column, nextValue)}
      />
    </td>
  );
}

function getValue(job: WorkspaceJob, path: string): unknown {
  return path.split(".").reduce<unknown>((current, segment) => {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    return (current as Record<string, unknown>)[segment];
  }, job.config);
}
