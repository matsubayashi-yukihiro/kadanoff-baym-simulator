from __future__ import annotations

import hashlib
import json
import os
import subprocess
from functools import lru_cache

from backend.app.schemas import (
    DecisionNoteCreate,
    DecisionNoteRecord,
    DerivedAnalysisArtifactCreate,
    DerivedAnalysisArtifactRecord,
    DerivedAnalysisSourceKind,
    EvidenceBundleCreate,
    EvidenceBundleRecord,
    JobGroupCreate,
    JobGroupRecord,
    RunDetail,
    RunResearchMetadata,
    RunResearchMetadataPatch,
    RunSummary,
    SimulationConfig,
    StudyCreate,
    StudyRecord,
    SweepCreate,
    SweepRecord,
)
from backend.app.storage.experiment_registry import ExperimentRegistry
from backend.app.storage.file_storage import FileRunStorage


class ExperimentRepository:
    def __init__(self, storage: FileRunStorage, registry: ExperimentRegistry) -> None:
        self.storage = storage
        self.registry = registry
        self.backfill_existing_runs()

    def create_run(self, config: SimulationConfig) -> RunSummary:
        summary = self.storage.create_run(config)
        metadata = self._hydrate_research_metadata(summary.research_metadata, run_id=summary.run_id, config=config)
        summary = self.storage.update_research_metadata(summary.run_id, metadata)
        self.registry.upsert_run(summary)
        return summary

    def list_runs(self) -> list[RunSummary]:
        return self.registry.list_runs()

    def read_run_detail(self, run_id: str) -> RunDetail:
        detail = self.storage.read_run_detail(run_id)
        try:
            metadata = self.registry.get_run_metadata(run_id)
        except FileNotFoundError:
            metadata = self._sync_run_from_storage(run_id)
        return detail.model_copy(update={"research_metadata": metadata})

    def update_status(self, *args, **kwargs):
        status = self.storage.update_status(*args, **kwargs)
        self._sync_run_from_storage(status.run_id)
        return status

    def attach_pid(self, run_id: str, pid: int) -> None:
        self.storage.attach_pid(run_id, pid)
        self._sync_run_from_storage(run_id)

    def write_results(self, run_id: str, **kwargs) -> None:
        self.storage.write_results(run_id, **kwargs)
        self._sync_run_from_storage(run_id)

    def append_log(self, run_id: str, message: str) -> None:
        self.storage.append_log(run_id, message)

    def read_log(self, run_id: str) -> str:
        self.storage.read_summary(run_id)
        return self.storage.read_log(run_id)

    def update_run_metadata(self, run_id: str, patch: RunResearchMetadataPatch) -> RunDetail:
        summary = self.storage.read_summary(run_id)
        config = self.storage.read_config(run_id)
        current = self._hydrate_research_metadata(summary.research_metadata, run_id=run_id, config=config)
        updates = patch.model_dump(exclude_unset=True)
        merged = current.model_copy(
            update={
                key: ([] if value is None and key in {"failure_tags", "tags"} else value)
                for key, value in updates.items()
            }
        )
        hydrated = self._hydrate_research_metadata(merged, run_id=run_id, config=config)
        updated_summary = self.storage.update_research_metadata(run_id, hydrated)
        self.registry.upsert_run(updated_summary)
        self.registry.refresh_parent_states_for_run(run_id)
        detail = self.storage.read_run_detail(run_id)
        return detail.model_copy(update={"research_metadata": hydrated})

    def create_study(self, payload: StudyCreate) -> StudyRecord:
        return self.registry.create_study(payload)

    def list_studies(self) -> list[StudyRecord]:
        return self.registry.list_studies()

    def get_study(self, study_id: str) -> StudyRecord:
        return self.registry.get_study(study_id)

    def create_job_group(self, payload: JobGroupCreate) -> JobGroupRecord:
        group = self.registry.create_job_group(payload)
        for run_id in payload.child_run_ids:
            self.update_run_metadata(
                run_id,
                RunResearchMetadataPatch(
                    study_id=payload.study_id,
                    group_id=group.group_id,
                ),
            )
        return self.registry.get_job_group(group.group_id)

    def list_job_groups(self, *, study_id: str | None = None) -> list[JobGroupRecord]:
        return self.registry.list_job_groups(study_id=study_id)

    def get_job_group(self, group_id: str) -> JobGroupRecord:
        return self.registry.get_job_group(group_id)

    def create_sweep(self, payload: SweepCreate) -> SweepRecord:
        sweep = self.registry.create_sweep(payload)
        for run_id in payload.child_run_ids:
            self.update_run_metadata(
                run_id,
                RunResearchMetadataPatch(
                    study_id=payload.study_id,
                    sweep_id=sweep.sweep_id,
                ),
            )
        return self.registry.get_sweep(sweep.sweep_id)

    def list_sweeps(self, *, study_id: str | None = None) -> list[SweepRecord]:
        return self.registry.list_sweeps(study_id=study_id)

    def get_sweep(self, sweep_id: str) -> SweepRecord:
        return self.registry.get_sweep(sweep_id)

    def create_decision_note(self, payload: DecisionNoteCreate) -> DecisionNoteRecord:
        return self.registry.create_decision_note(payload)

    def list_decision_notes(
        self,
        *,
        study_id: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> list[DecisionNoteRecord]:
        return self.registry.list_decision_notes(study_id=study_id, source_kind=source_kind, source_id=source_id)

    def get_decision_note(self, note_id: str) -> DecisionNoteRecord:
        return self.registry.get_decision_note(note_id)

    def create_derived_analysis(self, payload: DerivedAnalysisArtifactCreate) -> DerivedAnalysisArtifactRecord:
        return self.registry.create_derived_analysis(payload)

    def list_derived_analyses(
        self,
        *,
        study_id: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> list[DerivedAnalysisArtifactRecord]:
        return self.registry.list_derived_analyses(
            study_id=study_id,
            source_kind=None if source_kind is None else DerivedAnalysisSourceKind(source_kind),
            source_id=source_id,
        )

    def get_derived_analysis(self, analysis_id: str) -> DerivedAnalysisArtifactRecord:
        return self.registry.get_derived_analysis(analysis_id)

    def create_evidence_bundle(self, payload: EvidenceBundleCreate) -> EvidenceBundleRecord:
        return self.registry.create_evidence_bundle(payload)

    def list_evidence_bundles(self, *, study_id: str | None = None) -> list[EvidenceBundleRecord]:
        return self.registry.list_evidence_bundles(study_id=study_id)

    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundleRecord:
        return self.registry.get_evidence_bundle(bundle_id)

    def backfill_existing_runs(self) -> int:
        imported = 0
        for summary in self.storage.list_runs():
            config = self.storage.read_config(summary.run_id)
            metadata = self._hydrate_research_metadata(summary.research_metadata, run_id=summary.run_id, config=config)
            current = summary.research_metadata.model_dump(mode="json")
            hydrated = metadata.model_dump(mode="json")
            if current != hydrated:
                summary = self.storage.update_research_metadata(summary.run_id, metadata)
            self.registry.upsert_run(summary)
            imported += 1
        return imported

    def _sync_run_from_storage(self, run_id: str) -> RunResearchMetadata:
        summary = self.storage.read_summary(run_id)
        config = self.storage.read_config(run_id)
        metadata = self._hydrate_research_metadata(summary.research_metadata, run_id=run_id, config=config)
        if summary.research_metadata.model_dump(mode="json") != metadata.model_dump(mode="json"):
            summary = self.storage.update_research_metadata(run_id, metadata)
        self.registry.upsert_run(summary)
        self.registry.refresh_parent_states_for_run(run_id)
        return metadata

    def _hydrate_research_metadata(
        self,
        metadata: RunResearchMetadata,
        *,
        run_id: str,
        config: SimulationConfig,
    ) -> RunResearchMetadata:
        defaults = {
            "preset_id": config.name,
            "config_hash": _compute_config_hash(config),
            "code_version": _detect_code_version(),
            "storage_uri": str(self.storage.run_dir(run_id).resolve()),
        }
        return metadata.model_copy(
            update={
                key: value
                for key, value in defaults.items()
                if getattr(metadata, key) in {None, ""}
            }
        )


def _compute_config_hash(config: SimulationConfig) -> str:
    payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=1)
def _detect_code_version() -> str | None:
    env_value = os.getenv("TDKB_CODE_VERSION")
    if env_value:
        return env_value

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    value = result.stdout.strip()
    return value or None
