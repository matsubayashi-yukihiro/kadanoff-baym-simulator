from __future__ import annotations

from typing import Any

from backend.app.jobs.runner import JobRunner
from backend.app.schemas import (
    DecisionNoteCreate,
    DecisionNoteRecord,
    DerivedAnalysisArtifactCreate,
    DerivedAnalysisArtifactRecord,
    EvidenceBundleCreate,
    EvidenceBundleRecord,
    GreenFunctionCatalogResponse,
    GreenFunctionSliceResponse,
    JobGroupCreate,
    JobGroupRecord,
    MixedGreenFunctionCatalogResponse,
    MixedGreenFunctionSliceResponse,
    ObservableCatalogResponse,
    ObservableResponse,
    RunDetail,
    RunResearchMetadataPatch,
    RunState,
    RunSummary,
    SimulationConfig,
    StudyCreate,
    StudyRecord,
    SweepCreate,
    SweepRecord,
    ThermalBranchCatalogResponse,
    ThermalBranchSliceResponse,
)
from backend.app.schemas.simulation import PresetCategory, PresetEntry, PresetValidationStatus
from backend.app.storage.experiment_repository import ExperimentRepository


def build_default_preset() -> PresetEntry:
    return PresetEntry(
        name="square-4x4-baseline",
        category=PresetCategory.EXACT_BASELINE,
        validation_status=PresetValidationStatus.VALIDATED,
        summary="Exact one-body propagation for transport and energy-work sanity checks.",
        scope_note="Clean benchmark surface for currents, density transport, and dt convergence. Interaction fields are ignored by this solver.",
        primary_observable="density",
        config=SimulationConfig(
            name="square-4x4-baseline",
            lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
            time={"t_final": 1.0, "dt": 0.1},
            drive={
                "amplitude_x": 0.25,
                "amplitude_y": 0.0,
                "frequency": 3.0,
                "center": 0.5,
                "width": 0.3,
            },
            initial_state={"filling": 0.5, "temperature": 0.0},
        ),
    )


def build_tdhfb_preset() -> PresetEntry:
    return PresetEntry(
        name="square-4x4-bond-d-tdhfb",
        category=PresetCategory.MEAN_FIELD,
        validation_status=PresetValidationStatus.PARTIAL,
        summary="Pairing-enabled mean-field draft for stationary states and equal-time checks.",
        scope_note="Use for paired dynamics and for checking the equal-time bridge before KBE scattering closures.",
        primary_observable="pairing_d",
        config=SimulationConfig(
            name="square-4x4-bond-d-tdhfb",
            solver="tdhfb",
            lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
            time={"t_final": 1.0, "dt": 0.1},
            drive={"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            interaction={
                "onsite_u": -4.0,
                "nearest_neighbor_v": -2.5,
                "pairing_channel": "bond_d",
            },
            initial_state={"filling": 0.5, "temperature": 0.0, "seed_pairing": 0.2},
            observables=["density", "energy", "pairing", "pairing_s", "pairing_d"],
        ),
    )


def build_kbe_hfb_preset() -> PresetEntry:
    return PresetEntry(
        name="square-4x4-bond-d-kbe-hfb",
        category=PresetCategory.WORKING_BASELINE,
        validation_status=PresetValidationStatus.PARTIAL,
        summary="KBE-HFB scaffold with bond_d pairing for contour inspection and baseline anchoring.",
        scope_note="Primary working baseline for Higgs-oriented studies. Use to anchor compare runs and contour evidence.",
        primary_observable="pairing_d",
        config=SimulationConfig(
            name="square-4x4-bond-d-kbe-hfb",
            solver="kbe_hfb",
            lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
            time={"t_final": 1.0, "dt": 0.1},
            drive={"amplitude_x": 0.0, "amplitude_y": 0.0, "frequency": 0.0, "center": 0.0, "width": 1.0},
            interaction={
                "onsite_u": -4.0,
                "nearest_neighbor_v": -2.5,
                "pairing_channel": "bond_d",
            },
            initial_state={"filling": 0.5, "temperature": 0.0, "seed_pairing": 0.2},
            observables=["density", "energy", "pairing", "pairing_s", "pairing_d"],
        ),
    )


def build_higgs_demo_preset() -> PresetEntry:
    return PresetEntry(
        name="square-4x4-higgs-demo-kbe-hfb",
        category=PresetCategory.DEMO,
        validation_status=PresetValidationStatus.PROTOTYPE,
        summary="Long-window kbe_hfb + hfb + bond_d run with Gaussian pulse and pairing_d readout.",
        scope_note="Illustrative demo. Pulse and observation window tuned for readable traces and FFT preview. Numbers are provisional draft values.",
        primary_observable="pairing_d",
        config=SimulationConfig(
            name="square-4x4-higgs-demo-kbe-hfb",
            solver="kbe_hfb",
            lattice={"nx": 4, "ny": 4, "hopping": 1.0, "chemical_potential": 0.0},
            time={"t_final": 20.0, "dt": 0.05, "save_every": 1},
            drive={
                "amplitude_x": 0.25,
                "amplitude_y": 0.125,
                "frequency": 2.0,
                "phase": 0.0,
                "center": 3.0,
                "width": 1.2,
            },
            interaction={
                "onsite_u": -2.0,
                "nearest_neighbor_v": -2.5,
                "pairing_channel": "bond_d",
            },
            initial_state={"filling": 0.5, "temperature": 0.0, "seed_pairing": 0.2},
            kbe={"self_energy": "hfb"},
            observables=["density", "energy", "vector_potential", "pairing", "pairing_s", "pairing_d"],
        ),
    )


class RunService:
    def __init__(self, repository: ExperimentRepository, runner: JobRunner) -> None:
        self.repository = repository
        self.runner = runner

    def create_run(self, config: SimulationConfig) -> RunDetail:
        summary = self.repository.create_run(config)
        pid = self.runner.submit(summary.run_id, config, self.repository.storage.base_dir, self.repository.registry.db_path)
        if pid is not None:
            self.repository.attach_pid(summary.run_id, pid)
        return self.get_run(summary.run_id)

    def list_runs(self) -> list[RunSummary]:
        return self.repository.list_runs()

    def get_run(self, run_id: str) -> RunDetail:
        return self.repository.read_run_detail(run_id)

    def cancel_run(self, run_id: str) -> RunDetail:
        status = self.repository.storage.read_status(run_id)
        if status.state in {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}:
            return self.get_run(run_id)

        cancelled = self.runner.cancel(run_id)
        if cancelled or status.state == RunState.QUEUED:
            self.repository.update_status(run_id, RunState.CANCELLED, message="run cancelled")
        return self.get_run(run_id)

    def read_log(self, run_id: str) -> str:
        return self.repository.read_log(run_id)

    def update_run_metadata(self, run_id: str, patch: RunResearchMetadataPatch) -> RunDetail:
        return self.repository.update_run_metadata(run_id, patch)

    def list_observables(self, run_id: str) -> ObservableCatalogResponse:
        descriptors = self.repository.storage.read_observable_catalog(run_id)
        return ObservableCatalogResponse(run_id=run_id, observables=[item.name for item in descriptors])

    def get_observable(self, run_id: str, name: str) -> ObservableResponse:
        return self.repository.storage.read_observable(run_id, name)

    def list_green_functions(self, run_id: str) -> GreenFunctionCatalogResponse:
        return self.repository.storage.read_green_function_catalog(run_id)

    def get_green_function_slice(
        self,
        run_id: str,
        component: str,
        *,
        row_start: int | None = None,
        row_stop: int | None = None,
        col_start: int | None = None,
        col_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> GreenFunctionSliceResponse:
        return self.repository.storage.read_green_function_slice(
            run_id,
            component,
            row_start=row_start,
            row_stop=row_stop,
            col_start=col_start,
            col_stop=col_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )

    def list_thermal_branch(self, run_id: str) -> ThermalBranchCatalogResponse:
        return self.repository.storage.read_thermal_branch_catalog(run_id)

    def get_thermal_branch_slice(
        self,
        run_id: str,
        component: str,
        *,
        tau_start: int | None = None,
        tau_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> ThermalBranchSliceResponse:
        return self.repository.storage.read_thermal_branch_slice(
            run_id,
            component,
            tau_start=tau_start,
            tau_stop=tau_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )

    def list_mixed_green_functions(self, run_id: str) -> MixedGreenFunctionCatalogResponse:
        return self.repository.storage.read_mixed_green_function_catalog(run_id)

    def get_mixed_green_function_slice(
        self,
        run_id: str,
        component: str,
        *,
        time_start: int | None = None,
        time_stop: int | None = None,
        tau_start: int | None = None,
        tau_stop: int | None = None,
        nambu_start: int | None = None,
        nambu_stop: int | None = None,
    ) -> MixedGreenFunctionSliceResponse:
        return self.repository.storage.read_mixed_green_function_slice(
            run_id,
            component,
            time_start=time_start,
            time_stop=time_stop,
            tau_start=tau_start,
            tau_stop=tau_stop,
            nambu_start=nambu_start,
            nambu_stop=nambu_stop,
        )

    def get_presets(self) -> list[PresetEntry]:
        return [build_higgs_demo_preset(), build_default_preset(), build_tdhfb_preset(), build_kbe_hfb_preset()]

    def get_schema(self) -> dict[str, Any]:
        return SimulationConfig.model_json_schema()

    def create_study(self, payload: StudyCreate) -> StudyRecord:
        return self.repository.create_study(payload)

    def list_studies(self) -> list[StudyRecord]:
        return self.repository.list_studies()

    def get_study(self, study_id: str) -> StudyRecord:
        return self.repository.get_study(study_id)

    def create_job_group(self, payload: JobGroupCreate) -> JobGroupRecord:
        return self.repository.create_job_group(payload)

    def list_job_groups(self, *, study_id: str | None = None) -> list[JobGroupRecord]:
        return self.repository.list_job_groups(study_id=study_id)

    def get_job_group(self, group_id: str) -> JobGroupRecord:
        return self.repository.get_job_group(group_id)

    def create_sweep(self, payload: SweepCreate) -> SweepRecord:
        return self.repository.create_sweep(payload)

    def list_sweeps(self, *, study_id: str | None = None) -> list[SweepRecord]:
        return self.repository.list_sweeps(study_id=study_id)

    def get_sweep(self, sweep_id: str) -> SweepRecord:
        return self.repository.get_sweep(sweep_id)

    def create_decision_note(self, payload: DecisionNoteCreate) -> DecisionNoteRecord:
        return self.repository.create_decision_note(payload)

    def list_decision_notes(
        self,
        *,
        study_id: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> list[DecisionNoteRecord]:
        return self.repository.list_decision_notes(
            study_id=study_id,
            source_kind=source_kind,
            source_id=source_id,
        )

    def get_decision_note(self, note_id: str) -> DecisionNoteRecord:
        return self.repository.get_decision_note(note_id)

    def create_derived_analysis(self, payload: DerivedAnalysisArtifactCreate) -> DerivedAnalysisArtifactRecord:
        return self.repository.create_derived_analysis(payload)

    def list_derived_analyses(
        self,
        *,
        study_id: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> list[DerivedAnalysisArtifactRecord]:
        return self.repository.list_derived_analyses(
            study_id=study_id,
            source_kind=source_kind,
            source_id=source_id,
        )

    def get_derived_analysis(self, analysis_id: str) -> DerivedAnalysisArtifactRecord:
        return self.repository.get_derived_analysis(analysis_id)

    def create_evidence_bundle(self, payload: EvidenceBundleCreate) -> EvidenceBundleRecord:
        return self.repository.create_evidence_bundle(payload)

    def list_evidence_bundles(self, *, study_id: str | None = None) -> list[EvidenceBundleRecord]:
        return self.repository.list_evidence_bundles(study_id=study_id)

    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundleRecord:
        return self.repository.get_evidence_bundle(bundle_id)
