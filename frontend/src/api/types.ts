import type { components, paths } from "./generated";

export type SimulationConfigInput =
  paths["/api/v1/runs"]["post"]["requestBody"]["content"]["application/json"];
export type RunSummary = paths["/api/v1/runs"]["get"]["responses"][200]["content"]["application/json"][number];
export type RunDetail = paths["/api/v1/runs"]["post"]["responses"][202]["content"]["application/json"];
export type ObservableCatalogResponse =
  paths["/api/v1/runs/{run_id}/observables"]["get"]["responses"][200]["content"]["application/json"];
export type ObservableResponse =
  paths["/api/v1/runs/{run_id}/observables/{name}"]["get"]["responses"][200]["content"]["application/json"];
export type RunState = components["schemas"]["RunState"];
