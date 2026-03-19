import type { RunDetail } from "../api/types";

export type FailureCategory = "solver_error" | "validation_error" | "timeout" | "cancelled" | "unknown";

export type FailureInfo = {
  category: FailureCategory;
  summary: string;
  details: string[];
  suggestedAction: string;
};

export function analyzeFailure(run: RunDetail): FailureInfo | null {
  if (run.state !== "failed" && run.state !== "cancelled") return null;

  if (run.state === "cancelled") {
    return {
      category: "cancelled",
      summary: "Run was cancelled by user.",
      details: run.status_message ? [run.status_message] : [],
      suggestedAction: "Resubmit if the cancellation was unintended.",
    };
  }

  const message = (run.status_message ?? "").toLowerCase();
  const details: string[] = [];
  if (run.status_message) details.push(run.status_message);

  if (message.includes("nan")) {
    return {
      category: "solver_error",
      summary: "Solver produced NaN values.",
      details,
      suggestedAction: "Reduce dt or check interaction parameters for instability.",
    };
  }

  if (message.includes("convergence") || message.includes("did not converge")) {
    return {
      category: "solver_error",
      summary: "Fixed-point iteration did not converge.",
      details,
      suggestedAction: "Increase max_fixed_point_iterations or adjust mixing parameter.",
    };
  }

  if (message.includes("max iterations") || message.includes("exceeded")) {
    return {
      category: "solver_error",
      summary: "Maximum iteration count exceeded.",
      details,
      suggestedAction: "Increase iteration limit or loosen tolerance.",
    };
  }

  if (message.includes("timeout") || message.includes("timed out")) {
    return {
      category: "timeout",
      summary: "Run timed out.",
      details,
      suggestedAction: "Reduce t_final, increase dt, or use a smaller lattice.",
    };
  }

  if (message.includes("validation") || message.includes("schema") || message.includes("invalid")) {
    return {
      category: "validation_error",
      summary: "Configuration validation failed.",
      details,
      suggestedAction: "Check the configuration parameters for invalid values.",
    };
  }

  return {
    category: "unknown",
    summary: "Run failed with an unclassified error.",
    details,
    suggestedAction: "Check the run log for details.",
  };
}
