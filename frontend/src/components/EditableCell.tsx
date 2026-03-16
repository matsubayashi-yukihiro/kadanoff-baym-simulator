import { useEffect, useState } from "react";

import type { JobColumn } from "../lib/workspace";

type EditableCellProps = {
  jobLabel: string;
  column: JobColumn;
  value: unknown;
  onCommit: (value: unknown) => void;
};

export function EditableCell(props: EditableCellProps) {
  const { jobLabel, column, value, onCommit } = props;
  const [text, setText] = useState(formatDraftValue(value));

  useEffect(() => {
    setText(formatDraftValue(value));
  }, [value]);

  const parsed = parseDraftValue(column, text);
  const isInvalid = !parsed.valid;
  const fieldLabel = `${jobLabel} ${column.label}`;

  if (column.kind === "boolean") {
    return (
      <input
        aria-label={fieldLabel}
        className="cell-checkbox"
        type="checkbox"
        checked={Boolean(value)}
        onChange={(event) => onCommit(event.target.checked)}
      />
    );
  }

  if (column.kind === "enum") {
    return (
      <select
        aria-label={fieldLabel}
        className="cell-select"
        value={String(value ?? "")}
        onChange={(event) => onCommit(event.target.value)}
      >
        {(column.options ?? []).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  function commit() {
    if (!parsed.valid) {
      setText(formatDraftValue(value));
      return;
    }
    onCommit(parsed.value);
  }

  return (
    <input
      aria-label={fieldLabel}
      className={`cell-input ${isInvalid ? "cell-input-invalid" : ""}`}
      data-invalid={isInvalid}
      inputMode={column.kind === "integer" ? "numeric" : column.kind === "float" ? "decimal" : "text"}
      value={text}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          commit();
        }
        if (event.key === "Escape") {
          setText(formatDraftValue(value));
        }
      }}
    />
  );
}

function parseDraftValue(column: JobColumn, rawValue: string): { valid: boolean; value: unknown } {
  if (column.kind === "text") {
    return { valid: true, value: rawValue };
  }

  if (rawValue.trim() === "") {
    if (column.nullable) {
      return { valid: true, value: null };
    }
    return { valid: false, value: null };
  }

  if (column.kind === "integer") {
    if (!/^-?\d+$/.test(rawValue.trim())) {
      return { valid: false, value: null };
    }
    return { valid: true, value: Number.parseInt(rawValue, 10) };
  }

  if (column.kind === "float") {
    const parsed = Number(rawValue);
    return Number.isFinite(parsed) ? { valid: true, value: parsed } : { valid: false, value: null };
  }

  return { valid: true, value: rawValue };
}

function formatDraftValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}
