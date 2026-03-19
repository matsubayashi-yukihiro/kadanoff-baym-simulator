import { ApiError } from "../api/client";
import type { RunDetail, RunSummary } from "../api/types";

export function sortRuns(runs: RunSummary[]): RunSummary[] {
  return [...runs].sort((left, right) => getRunSortKey(right) - getRunSortKey(left));
}

function getRunSortKey(run: RunSummary): number {
  return Date.parse(run.updated_at ?? "") || Date.parse(run.created_at ?? "") || 0;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function isTerminalState(state: RunDetail["state"]): boolean {
  return state === "succeeded" || state === "failed" || state === "cancelled";
}

export function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "request failed";
}
