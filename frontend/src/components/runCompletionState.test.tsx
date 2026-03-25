import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import type { RunDetail } from "../api/types";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { GreenFunctionPanel } from "./GreenFunctionPanel";
import { KSpectralPanel } from "./KSpectralPanel";
import { ObservablePanel } from "./ObservablePanel";
import { useDerivedAnalysis } from "../hooks/useDerivedAnalysis";

vi.mock("../hooks/useDerivedAnalysis", () => ({
  useDerivedAnalysis: vi.fn(),
}));

vi.mock("../hooks/useBackendCapabilities", () => ({
  useBackendCapabilities: () => ({
    capabilities: {
      supportsEquilibriumPayload: true,
      supportsDerivedAnalysisLaunch: true,
      supportsDerivedAnalysisRunKspace: true,
    },
    loading: false,
    error: null,
  }),
}));

const launchMock = vi.fn();

function makeRun(partial: Partial<RunDetail> = {}): RunDetail {
  return {
    run_id: "run-warning-1",
    name: "kspace-warning-run",
    solver: "kbe_hfb",
    state: "succeeded_with_warnings",
    created_at: "2026-03-23T00:00:00Z",
    updated_at: "2026-03-23T00:01:00Z",
    started_at: "2026-03-23T00:00:05Z",
    finished_at: "2026-03-23T00:00:55Z",
    status_message: "simulation completed",
    lattice: { nx: 2, ny: 2 },
    time_grid: { dt: 0.1, t_final: 0.2 },
    available_observables: [],
    diagnostics_excerpt: {},
    diagnostics: {},
    config: {
      solver: "kbe_hfb",
      representation: "k_space",
      kbe: { self_energy: "second_born_reference" },
      thermal_branch: { enabled: true },
    },
    ...partial,
  } as RunDetail;
}

describe("warning completion UI gates", () => {
  beforeEach(() => {
    launchMock.mockReset();
    vi.mocked(useDerivedAnalysis).mockReturnValue({
      analysis: null,
      result: null,
      status: "idle",
      error: null,
      launch: launchMock,
    });
  });

  it("unlocks observable panel for succeeded_with_warnings", () => {
    render(
      <ObservablePanel
        catalog={{ run_id: "run-warning-1", observables: ["density"] }}
        catalogLoading={false}
        catalogError={null}
        data={null}
        dataLoading={false}
        dataError={null}
        run={makeRun({ solver: "tdhfb" })}
        selectedObservable="density"
        onSelectObservable={() => {}}
        overlayNames={new Set()}
        onToggleOverlay={() => {}}
        overlayData={new Map()}
      />,
    );

    expect(screen.queryByText(/Observables will unlock after the run completes/i)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button").length).toBeGreaterThan(0);
  });

  it("unlocks green-function panel for succeeded_with_warnings", () => {
    render(
      <GreenFunctionPanel
        run={makeRun()}
        catalog={{
          run_id: "run-warning-1",
          components: ["retarded", "lesser"],
          time_point_count: 3,
          shape: [3, 3, 2, 2],
          nambu_dimension: 2,
        }}
        catalogLoading={false}
        catalogError={null}
        selectedComponent="retarded"
        onSelectComponent={() => {}}
        rowIndex={0}
        colIndex={0}
        nambuStart={0}
        nambuWindow={2}
        onRowIndexChange={() => {}}
        onColIndexChange={() => {}}
        onNambuStartChange={() => {}}
        onNambuWindowChange={() => {}}
        slice={null}
        sliceLoading={false}
        sliceError={null}
      />,
    );

    expect(screen.queryByText(/Green-function slices will unlock after the run completes/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retarded" })).toBeInTheDocument();
  });

  it("enables k-space derived panel for succeeded_with_warnings", () => {
    render(<KSpectralPanel run={makeRun()} studyId="study-1" />);

    expect(screen.getByRole("button", { name: "Compute" })).toBeEnabled();
  });

  it("shows explicit fallback warning when k-space path falls back to full matrix", () => {
    render(
      <DiagnosticsPanel
        run={makeRun({
          diagnostics: {
            k_space_path_mode: "full_matrix_fallback",
            k_space_path_fallback_reason: "one_body_not_block_diagonal",
            second_born_kspace_block_path: false,
          },
        })}
      />,
    );

    expect(screen.getByText(/k-space block path is inactive and fallback is in effect/i)).toBeInTheDocument();
    expect(screen.getAllByText(/one_body_not_block_diagonal/i).length).toBeGreaterThan(0);
  });
});
