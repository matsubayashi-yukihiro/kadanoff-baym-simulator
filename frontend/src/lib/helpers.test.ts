import { describe, expect, it } from "vitest";

import { isSuccessfulState, isTerminalState } from "./helpers";

describe("run state helpers", () => {
  it("treats succeeded_with_warnings as successful and terminal", () => {
    expect(isSuccessfulState("succeeded")).toBe(true);
    expect(isSuccessfulState("succeeded_with_warnings")).toBe(true);
    expect(isTerminalState("succeeded_with_warnings")).toBe(true);
  });

  it("keeps failed/cancelled terminal but not successful", () => {
    expect(isSuccessfulState("failed")).toBe(false);
    expect(isSuccessfulState("cancelled")).toBe(false);
    expect(isTerminalState("failed")).toBe(true);
    expect(isTerminalState("cancelled")).toBe(true);
  });

  it("keeps queued/running non-terminal", () => {
    expect(isTerminalState("queued")).toBe(false);
    expect(isTerminalState("running")).toBe(false);
  });
});
