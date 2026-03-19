import type { components, paths } from "./generated";

export type SimulationConfigInput = components["schemas"]["SimulationConfig-Input"];
export type PresetConfig = components["schemas"]["SimulationConfig-Output"];
export type RunSummary = paths["/api/v1/runs"]["get"]["responses"][200]["content"]["application/json"][number];
export type RunDetail = paths["/api/v1/runs"]["post"]["responses"][202]["content"]["application/json"];
export type PresetListResponse = paths["/api/v1/presets"]["get"]["responses"][200]["content"]["application/json"];
export type ObservableCatalogResponse =
  paths["/api/v1/runs/{run_id}/observables"]["get"]["responses"][200]["content"]["application/json"];
export type ObservableResponse =
  paths["/api/v1/runs/{run_id}/observables/{name}"]["get"]["responses"][200]["content"]["application/json"];
export type GreenFunctionCatalogResponse =
  paths["/api/v1/runs/{run_id}/green-functions"]["get"]["responses"][200]["content"]["application/json"];
export type GreenFunctionSliceResponse =
  paths["/api/v1/runs/{run_id}/green-functions/{component}"]["get"]["responses"][200]["content"]["application/json"];
export type ThermalBranchCatalogResponse =
  paths["/api/v1/runs/{run_id}/thermal-branch"]["get"]["responses"][200]["content"]["application/json"];
export type ThermalBranchSliceResponse =
  paths["/api/v1/runs/{run_id}/thermal-branch/{component}"]["get"]["responses"][200]["content"]["application/json"];
export type MixedGreenFunctionCatalogResponse =
  paths["/api/v1/runs/{run_id}/mixed-green-functions"]["get"]["responses"][200]["content"]["application/json"];
export type MixedGreenFunctionSliceResponse =
  paths["/api/v1/runs/{run_id}/mixed-green-functions/{component}"]["get"]["responses"][200]["content"]["application/json"];
export type RunState = components["schemas"]["RunState"];
