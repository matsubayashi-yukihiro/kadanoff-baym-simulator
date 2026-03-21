import type { components, paths } from "./generated";

export type SimulationConfigInput = components["schemas"]["SimulationConfig-Input"];
/** @deprecated Use PresetEntry instead. Kept for internal config-only usage. */
export type PresetConfig = components["schemas"]["SimulationConfig-Output"];
export type PresetEntry = components["schemas"]["PresetEntry"];
export type PresetCategory = components["schemas"]["PresetCategory"];
export type PresetValidationStatus = components["schemas"]["PresetValidationStatus"];
export type SolverRepresentation = components["schemas"]["SolverRepresentation"];
export type RunSummary = paths["/api/v1/runs"]["get"]["responses"][200]["content"]["application/json"][number];
export type RunDetail = paths["/api/v1/runs"]["post"]["responses"][202]["content"]["application/json"];
export type RunProgressRecord =
  paths["/api/v1/runs/{run_id}/progress"]["get"]["responses"][200]["content"]["application/json"];
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
export type RunProgressPhase = components["schemas"]["RunProgressPhase"];
export type RunResearchMetadata = components["schemas"]["RunResearchMetadata"];
export type RunResearchMetadataPatch = components["schemas"]["RunResearchMetadataPatch"];
export type StudyRecord = components["schemas"]["StudyRecord"];
export type StudyCreate = components["schemas"]["StudyCreate"];
export type StudyStatus = components["schemas"]["StudyStatus"];
export type DecisionNoteRecord = components["schemas"]["DecisionNoteRecord"];
export type DecisionNoteCreate = components["schemas"]["DecisionNoteCreate"];
export type DecisionNoteKind = components["schemas"]["DecisionNoteKind"];
export type EvidenceBundleRecord = components["schemas"]["EvidenceBundleRecord"];
export type EvidenceBundleCreate = components["schemas"]["EvidenceBundleCreate"];
export type EvidenceBundlePatch = components["schemas"]["EvidenceBundlePatch"];
export type EvidenceBundleStatus = components["schemas"]["EvidenceBundleStatus"];
export type EvidenceBundleResolvedRecord = components["schemas"]["EvidenceBundleResolvedRecord"];
export type JobGroupRecord = components["schemas"]["JobGroupRecord"];
export type JobGroupCreate = components["schemas"]["JobGroupCreate"];
export type JobGroupLaunchRequest = components["schemas"]["JobGroupLaunchRequest"];
export type JobGroupVariant = components["schemas"]["JobGroupVariant"];
export type ComparisonKind = components["schemas"]["ComparisonKind"];
export type SweepRecord = components["schemas"]["SweepRecord"];
export type SweepCreate = components["schemas"]["SweepCreate"];
export type SweepLaunchRequest = components["schemas"]["SweepLaunchRequest"];
export type ParameterKind = components["schemas"]["ParameterKind"];
export type DerivedAnalysisArtifactRecord = components["schemas"]["DerivedAnalysisArtifactRecord"];
export type DerivedAnalysisLaunchRequest = components["schemas"]["DerivedAnalysisLaunchRequest"];
export type DerivedAnalysisResultRecord = components["schemas"]["DerivedAnalysisResultRecord"];
export type DerivedAnalysisSourceKind = components["schemas"]["DerivedAnalysisSourceKind"];
export type ArtifactLifecycleState = components["schemas"]["ArtifactLifecycleState"];
