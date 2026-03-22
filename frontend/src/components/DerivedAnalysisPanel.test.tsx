import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DerivedAnalysisPanel } from "./DerivedAnalysisPanel";

describe("DerivedAnalysisPanel", () => {
  it("shows unavailable reason and disables Compute when capability is missing", () => {
    const onLaunch = vi.fn();
    render(
      <DerivedAnalysisPanel
        title="K-Path Spectral Function"
        status="idle"
        error={null}
        result={null}
        onLaunch={onLaunch}
        unavailableReason="Backend capability missing"
      />,
    );

    expect(screen.getByText("Backend capability missing")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Unavailable" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onLaunch).not.toHaveBeenCalled();
  });
});

