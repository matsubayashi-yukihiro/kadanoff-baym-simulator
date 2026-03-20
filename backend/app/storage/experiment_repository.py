from __future__ import annotations

import hashlib
import json
import os
import subprocess
from functools import lru_cache

import numpy as np

from backend.app.schemas import (
    ArtifactLifecycleState,
    DecisionNoteCreate,
    DecisionNoteRecord,
    DerivedAnalysisArtifactCreate,
    DerivedAnalysisArtifactRecord,
    DerivedAnalysisLaunchRequest,
    DerivedAnalysisResultRecord,
    DerivedAnalysisSourceKind,
    EvidenceBundleCreate,
    EvidenceBundlePatch,
    EvidenceBundleResolvedAnalysis,
    EvidenceBundleResolvedArtifact,
    EvidenceBundleResolvedRecord,
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
        variant_labels_by_run_id = {
            variant.run_id: variant.label
            for variant in payload.variants
            if variant.run_id is not None
        }
        for run_id in payload.child_run_ids:
            self.update_run_metadata(
                run_id,
                RunResearchMetadataPatch(
                    study_id=payload.study_id,
                    group_id=group.group_id,
                    variant_label=variant_labels_by_run_id.get(run_id),
                ),
            )
        return self.registry.get_job_group(group.group_id)

    def list_job_groups(self, *, study_id: str | None = None) -> list[JobGroupRecord]:
        return self.registry.list_job_groups(study_id=study_id)

    def get_job_group(self, group_id: str) -> JobGroupRecord:
        return self.registry.get_job_group(group_id)

    def create_sweep(self, payload: SweepCreate) -> SweepRecord:
        sweep = self.registry.create_sweep(payload)
        for ordinal, run_id in enumerate(payload.child_run_ids):
            self.update_run_metadata(
                run_id,
                RunResearchMetadataPatch(
                    study_id=payload.study_id,
                    sweep_id=sweep.sweep_id,
                    variant_label=f"{payload.parameter_label}={payload.values[ordinal]}",
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

    def launch_derived_analysis(self, payload: DerivedAnalysisLaunchRequest) -> DerivedAnalysisArtifactRecord:
        cached = self._find_cached_derived_analysis(payload)
        if cached is not None and cached.data_refs:
            try:
                self.storage.read_derived_analysis_result(cached)
            except FileNotFoundError:
                pass
            else:
                return cached

        fft_payload, payload_kind, result_metadata = self._materialize_derived_analysis_payload(payload)
        analysis = self.registry.create_derived_analysis(
            DerivedAnalysisArtifactCreate(
                study_id=payload.study_id,
                source_kind=payload.source_kind,
                source_id=payload.source_id,
                analysis_type=payload.analysis_type,
                analysis_version=payload.analysis_version,
                cache_key=_build_analysis_cache_key(payload),
                parameters=dict(payload.parameters),
                status=ArtifactLifecycleState.SUCCEEDED,
                input_surface_ids=list(payload.input_surface_ids) or [payload.source_id],
                result_metadata=result_metadata,
                data_refs=[],
                supports_bundle_ids=[],
            )
        )
        data_ref = self.storage.write_derived_analysis_result(
            analysis.analysis_id,
            payload_kind=payload_kind,
            payload=fft_payload,
        )
        return self.registry.update_derived_analysis(
            analysis.model_copy(
                update={
                    "data_refs": [data_ref],
                }
            )
        )

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

    def get_derived_analysis_result(self, analysis_id: str) -> DerivedAnalysisResultRecord:
        analysis = self.registry.get_derived_analysis(analysis_id)
        return self.storage.read_derived_analysis_result(analysis)

    def create_evidence_bundle(self, payload: EvidenceBundleCreate) -> EvidenceBundleRecord:
        analysis_ids = self._validate_evidence_bundle_references(payload)
        bundle = self.registry.create_evidence_bundle(payload)
        self._sync_bundle_support_links(bundle.bundle_id, before_analysis_ids=[], after_analysis_ids=analysis_ids)
        return bundle

    def list_evidence_bundles(
        self,
        *,
        study_id: str | None = None,
        status: EvidenceBundleStatus | None = None,
    ) -> list[EvidenceBundleRecord]:
        return self.registry.list_evidence_bundles(study_id=study_id, status=status)

    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundleRecord:
        return self.registry.get_evidence_bundle(bundle_id)

    def update_evidence_bundle(self, bundle_id: str, patch: EvidenceBundlePatch) -> EvidenceBundleRecord:
        current = self.registry.get_evidence_bundle(bundle_id)
        updates = patch.model_dump(exclude_unset=True)
        candidate = current.model_copy(update=updates)
        validated_payload = EvidenceBundleCreate(
            study_id=current.study_id,
            title=candidate.title,
            claim_candidate=candidate.claim_candidate,
            artifact_refs=candidate.artifact_refs,
            analysis_refs=candidate.analysis_refs,
            validation_scope=candidate.validation_scope,
            reproduction_recipe=candidate.reproduction_recipe,
            status=candidate.status,
        )
        analysis_ids = self._validate_evidence_bundle_references(validated_payload)
        updated = self.registry.update_evidence_bundle(candidate)
        before_analysis_ids = self._collect_bundle_analysis_ids(current)
        self._sync_bundle_support_links(
            bundle_id,
            before_analysis_ids=before_analysis_ids,
            after_analysis_ids=analysis_ids,
        )
        return updated

    def get_evidence_bundle_resolved(self, bundle_id: str) -> EvidenceBundleResolvedRecord:
        bundle = self.registry.get_evidence_bundle(bundle_id)
        resolved_artifacts: list[EvidenceBundleResolvedArtifact] = []
        for artifact_ref in bundle.artifact_refs:
            if artifact_ref.artifact_kind.value == "run":
                run = self.read_run_detail(artifact_ref.artifact_id)
                resolved_artifacts.append(
                    EvidenceBundleResolvedArtifact(
                        artifact_kind=artifact_ref.artifact_kind,
                        artifact_id=artifact_ref.artifact_id,
                        study_id=run.research_metadata.study_id,
                        label=run.name or run.run_id,
                        state=run.state.value,
                        metadata={
                            "solver": run.solver,
                            "run_role": None if run.research_metadata.run_role is None else run.research_metadata.run_role.value,
                            "validation_status": run.research_metadata.validation_status.value,
                        },
                    )
                )
                continue
            if artifact_ref.artifact_kind.value == "job_group":
                group = self.get_job_group(artifact_ref.artifact_id)
                resolved_artifacts.append(
                    EvidenceBundleResolvedArtifact(
                        artifact_kind=artifact_ref.artifact_kind,
                        artifact_id=artifact_ref.artifact_id,
                        study_id=group.study_id,
                        label=group.name,
                        state=group.state.value,
                        metadata={
                            "comparison_kind": group.comparison_kind.value,
                            "baseline_run_id": group.baseline_run_id,
                            "child_run_count": len(group.child_run_ids),
                        },
                    )
                )
                continue
            if artifact_ref.artifact_kind.value == "sweep":
                sweep = self.get_sweep(artifact_ref.artifact_id)
                resolved_artifacts.append(
                    EvidenceBundleResolvedArtifact(
                        artifact_kind=artifact_ref.artifact_kind,
                        artifact_id=artifact_ref.artifact_id,
                        study_id=sweep.study_id,
                        label=sweep.name,
                        state=sweep.state.value,
                        metadata={
                            "parameter_kind": sweep.parameter_kind.value,
                            "parameter_label": sweep.parameter_label,
                            "child_run_count": len(sweep.child_run_ids),
                        },
                    )
                )
                continue
            if artifact_ref.artifact_kind.value == "analysis":
                analysis = self.get_derived_analysis(artifact_ref.artifact_id)
                resolved_artifacts.append(
                    EvidenceBundleResolvedArtifact(
                        artifact_kind=artifact_ref.artifact_kind,
                        artifact_id=artifact_ref.artifact_id,
                        study_id=analysis.study_id,
                        label=analysis.analysis_type,
                        state=analysis.status.value,
                        metadata={
                            "analysis_version": analysis.analysis_version,
                            "source_kind": analysis.source_kind.value,
                            "source_id": analysis.source_id,
                        },
                    )
                )

        seen_analysis_ids: set[str] = set()
        resolved_analyses: list[EvidenceBundleResolvedAnalysis] = []
        for analysis_id in [*bundle.analysis_refs, *[ref.artifact_id for ref in bundle.artifact_refs if ref.artifact_kind.value == "analysis"]]:
            if analysis_id in seen_analysis_ids:
                continue
            seen_analysis_ids.add(analysis_id)
            analysis = self.get_derived_analysis(analysis_id)
            resolved_analyses.append(
                EvidenceBundleResolvedAnalysis(
                    analysis_id=analysis.analysis_id,
                    study_id=analysis.study_id,
                    analysis_type=analysis.analysis_type,
                    analysis_version=analysis.analysis_version,
                    source_kind=analysis.source_kind,
                    source_id=analysis.source_id,
                    status=analysis.status,
                    result_metadata=analysis.result_metadata,
                    supports_bundle_ids=analysis.supports_bundle_ids,
                )
            )
        return EvidenceBundleResolvedRecord(
            bundle=bundle,
            resolved_artifacts=resolved_artifacts,
            resolved_analyses=resolved_analyses,
        )

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

    def _find_cached_derived_analysis(
        self,
        payload: DerivedAnalysisLaunchRequest,
    ) -> DerivedAnalysisArtifactRecord | None:
        cache_key = _build_analysis_cache_key(payload)
        matches = self.registry.list_derived_analyses(
            study_id=payload.study_id,
            source_kind=payload.source_kind,
            source_id=payload.source_id,
        )
        for candidate in matches:
            if (
                candidate.analysis_type == payload.analysis_type
                and candidate.analysis_version == payload.analysis_version
                and candidate.cache_key == cache_key
            ):
                return candidate
        return None

    def _validate_evidence_bundle_references(self, payload: EvidenceBundleCreate) -> list[str]:
        analysis_ids: list[str] = []
        for artifact_ref in payload.artifact_refs:
            if artifact_ref.artifact_kind.value == "run":
                record = self.read_run_detail(artifact_ref.artifact_id)
                reference_study_id = record.research_metadata.study_id
            elif artifact_ref.artifact_kind.value == "job_group":
                record = self.get_job_group(artifact_ref.artifact_id)
                reference_study_id = record.study_id
            elif artifact_ref.artifact_kind.value == "sweep":
                record = self.get_sweep(artifact_ref.artifact_id)
                reference_study_id = record.study_id
            elif artifact_ref.artifact_kind.value == "analysis":
                record = self.get_derived_analysis(artifact_ref.artifact_id)
                reference_study_id = record.study_id
                analysis_ids.append(record.analysis_id)
            else:
                raise ValueError(f"unsupported artifact reference kind: {artifact_ref.artifact_kind}")

            if reference_study_id is not None and reference_study_id != payload.study_id:
                raise ValueError("evidence bundle references must belong to the same study")

        for analysis_id in payload.analysis_refs:
            analysis = self.get_derived_analysis(analysis_id)
            if analysis.study_id != payload.study_id:
                raise ValueError("evidence bundle references must belong to the same study")
            analysis_ids.append(analysis.analysis_id)

        seen: set[str] = set()
        ordered_unique_analysis_ids: list[str] = []
        for analysis_id in analysis_ids:
            if analysis_id in seen:
                continue
            seen.add(analysis_id)
            ordered_unique_analysis_ids.append(analysis_id)
        return ordered_unique_analysis_ids

    def _collect_bundle_analysis_ids(self, bundle: EvidenceBundleRecord) -> list[str]:
        analysis_ids = list(bundle.analysis_refs)
        for artifact_ref in bundle.artifact_refs:
            if artifact_ref.artifact_kind.value == "analysis":
                analysis_ids.append(artifact_ref.artifact_id)
        ordered: list[str] = []
        seen: set[str] = set()
        for analysis_id in analysis_ids:
            if analysis_id in seen:
                continue
            seen.add(analysis_id)
            ordered.append(analysis_id)
        return ordered

    def _sync_bundle_support_links(
        self,
        bundle_id: str,
        *,
        before_analysis_ids: list[str],
        after_analysis_ids: list[str],
    ) -> None:
        before_set = set(before_analysis_ids)
        after_set = set(after_analysis_ids)

        for analysis_id in sorted(before_set - after_set):
            analysis = self.registry.get_derived_analysis(analysis_id)
            if bundle_id not in analysis.supports_bundle_ids:
                continue
            self.registry.update_derived_analysis(
                analysis.model_copy(
                    update={
                        "supports_bundle_ids": [item for item in analysis.supports_bundle_ids if item != bundle_id],
                    }
                )
            )

        for analysis_id in sorted(after_set):
            analysis = self.registry.get_derived_analysis(analysis_id)
            if bundle_id in analysis.supports_bundle_ids:
                continue
            self.registry.update_derived_analysis(
                analysis.model_copy(
                    update={
                        "supports_bundle_ids": [*analysis.supports_bundle_ids, bundle_id],
                    }
                )
            )

    def _materialize_derived_analysis_payload(
        self,
        payload: DerivedAnalysisLaunchRequest,
    ) -> tuple[dict[str, object], str, dict[str, object]]:
        observable_name = str(payload.parameters.get("observable") or "")
        if not observable_name:
            raise ValueError("derived-analysis launch requires parameters.observable")

        series_label = payload.parameters.get("series_label")
        if payload.source_kind == DerivedAnalysisSourceKind.RUN and payload.analysis_type == "fft_preview":
            fft_payload = _build_run_fft_payload(self.storage, payload.source_id, observable_name, series_label=series_label)
            return (
                fft_payload["observable"],
                "observable",
                {
                    "observable": observable_name,
                    "series_label": fft_payload["source_series_label"],
                    "sample_count": fft_payload["sample_count"],
                    "frequency_resolution": fft_payload["frequency_resolution"],
                    "dominant_frequency": fft_payload["dominant_frequency"],
                    "mean_subtracted": True,
                },
            )

        if payload.source_kind == DerivedAnalysisSourceKind.JOB_GROUP and payload.analysis_type == "fft_compare":
            group = self.get_job_group(payload.source_id)
            compare_payload = _build_job_group_fft_compare_payload(
                self.storage,
                group,
                observable_name=observable_name,
                series_label=series_label,
            )
            return (
                compare_payload,
                "comparison",
                {
                    "observable": observable_name,
                    "run_count": len(compare_payload["entries"]),
                    "baseline_run_id": group.baseline_run_id,
                    "comparison_kind": group.comparison_kind.value,
                },
            )

        if payload.source_kind == DerivedAnalysisSourceKind.SWEEP and payload.analysis_type == "fft_heatmap":
            sweep = self.get_sweep(payload.source_id)
            heatmap_payload = _build_sweep_fft_heatmap_payload(
                self.storage,
                sweep,
                observable_name=observable_name,
                series_label=series_label,
            )
            return (
                heatmap_payload,
                "heatmap",
                {
                    "observable": observable_name,
                    "sweep_point_count": len(sweep.child_run_ids),
                    "parameter_label": sweep.parameter_label,
                    "parameter_path": sweep.parameter_path,
                    "frequency_count": len(heatmap_payload["frequency"]),
                    "interpolated_to_common_grid": bool(heatmap_payload["interpolated_to_common_grid"]),
                },
            )

        raise ValueError(
            "derived-analysis launch currently supports run/fft_preview, job_group/fft_compare, and sweep/fft_heatmap only"
        )


def _compute_config_hash(config: SimulationConfig) -> str:
    payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_analysis_cache_key(payload: DerivedAnalysisLaunchRequest) -> str:
    cache_payload = json.dumps(
        {
            "study_id": payload.study_id,
            "source_kind": payload.source_kind.value,
            "source_id": payload.source_id,
            "analysis_type": payload.analysis_type,
            "analysis_version": payload.analysis_version,
            "parameters": payload.parameters,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(cache_payload).hexdigest()


def _build_run_fft_payload(
    storage: FileRunStorage,
    run_id: str,
    observable_name: str,
    *,
    series_label: object | None,
) -> dict[str, object]:
    source_observable = storage.read_observable(run_id, observable_name)
    return _build_fft_preview_payload(source_observable.model_dump(mode="json"), series_label=series_label)


def _build_job_group_fft_compare_payload(
    storage: FileRunStorage,
    group: JobGroupRecord,
    *,
    observable_name: str,
    series_label: object | None,
) -> dict[str, object]:
    label_by_run_id = {
        variant.run_id: variant.label
        for variant in group.variants
        if variant.run_id is not None
    }
    entries: list[dict[str, object]] = []
    for run_id in group.child_run_ids:
        fft_payload = _build_run_fft_payload(storage, run_id, observable_name, series_label=series_label)
        observable_payload = fft_payload["observable"]
        entries.append(
            {
                "run_id": run_id,
                "label": label_by_run_id.get(run_id, run_id),
                "frequency": observable_payload["time"],
                "magnitude": observable_payload["series"][0]["values"],
                "dominant_frequency": fft_payload["dominant_frequency"],
                "sample_count": fft_payload["sample_count"],
                "source_series_label": fft_payload["source_series_label"],
                "is_baseline": run_id == group.baseline_run_id,
            }
        )
    return {
        "name": f"{observable_name}_fft_compare",
        "source_kind": "job_group",
        "source_id": group.group_id,
        "observable": observable_name,
        "baseline_run_id": group.baseline_run_id,
        "comparison_kind": group.comparison_kind.value,
        "entries": entries,
    }


def _build_sweep_fft_heatmap_payload(
    storage: FileRunStorage,
    sweep: SweepRecord,
    *,
    observable_name: str,
    series_label: object | None,
) -> dict[str, object]:
    fft_rows: list[dict[str, object]] = []
    for run_id, parameter_value in zip(sweep.child_run_ids, sweep.values, strict=True):
        fft_payload = _build_run_fft_payload(storage, run_id, observable_name, series_label=series_label)
        observable_payload = fft_payload["observable"]
        fft_rows.append(
            {
                "run_id": run_id,
                "parameter_value": parameter_value,
                "frequency": [float(value) for value in observable_payload["time"]],
                "magnitude": [float(value) for value in observable_payload["series"][0]["values"]],
                "dominant_frequency": fft_payload["dominant_frequency"],
                "source_series_label": fft_payload["source_series_label"],
            }
        )

    reference_row = max(fft_rows, key=lambda row: len(row["frequency"]))
    common_frequency = np.asarray(reference_row["frequency"], dtype=float)
    intensity_rows: list[list[float]] = []
    interpolated_to_common_grid = False
    for row in fft_rows:
        frequency = np.asarray(row["frequency"], dtype=float)
        magnitude = np.asarray(row["magnitude"], dtype=float)
        if frequency.shape != common_frequency.shape or not np.allclose(frequency, common_frequency):
            interpolated_to_common_grid = True
            magnitude = np.interp(common_frequency, frequency, magnitude, left=0.0, right=0.0)
        intensity_rows.append(magnitude.astype(float).tolist())

    return {
        "name": f"{observable_name}_fft_heatmap",
        "source_kind": "sweep",
        "source_id": sweep.sweep_id,
        "observable": observable_name,
        "parameter_label": sweep.parameter_label,
        "parameter_path": sweep.parameter_path,
        "parameter_kind": sweep.parameter_kind.value,
        "parameter_values": list(sweep.values),
        "frequency": common_frequency.astype(float).tolist(),
        "intensity": intensity_rows,
        "run_ids": list(sweep.child_run_ids),
        "dominant_frequencies": [row["dominant_frequency"] for row in fft_rows],
        "interpolated_to_common_grid": interpolated_to_common_grid,
    }


def _build_fft_preview_payload(source_observable: dict[str, object], *, series_label: object | None) -> dict[str, object]:
    times = [float(value) for value in source_observable["time"]]
    dt = _infer_uniform_step(times)
    if dt is None:
        raise ValueError("fft_preview requires at least two uniformly spaced samples")

    series_entries = list(source_observable["series"])
    selected_series = None
    if isinstance(series_label, str):
        selected_series = next((series for series in series_entries if series["label"] == series_label), None)
    if selected_series is None:
        source_name = str(source_observable["name"])
        if source_name.startswith("pairing"):
            selected_series = next((series for series in series_entries if series["label"] == "magnitude"), None)
    if selected_series is None and series_entries:
        selected_series = series_entries[0]
    if selected_series is None:
        raise ValueError("fft_preview requires at least one observable series")

    values = [float(value) for value in selected_series["values"][: len(times)]]
    sample_count = min(len(times), len(values))
    if sample_count < 2:
        raise ValueError("fft_preview requires at least two samples in the selected series")

    values = values[:sample_count]
    mean_value = float(sum(values) / sample_count)
    centered = np.asarray(values, dtype=float) - mean_value
    spectrum = np.fft.rfft(centered)
    frequencies = np.fft.rfftfreq(sample_count, d=dt)
    magnitudes = np.abs(spectrum) / sample_count
    dominant_frequency = None
    if magnitudes.shape[0] > 1:
        dominant_index = int(np.argmax(magnitudes[1:]) + 1)
        dominant_frequency = float(frequencies[dominant_index])
    elif magnitudes.shape[0] == 1:
        dominant_frequency = float(frequencies[0])

    return {
        "observable": {
            "name": f"{source_observable['name']}_fft_preview",
            "time": frequencies.astype(float).tolist(),
            "series": [
                {
                    "label": f"{selected_series['label']} magnitude",
                    "values": magnitudes.astype(float).tolist(),
                }
            ],
            "units": source_observable.get("units"),
            "metadata": {
                **dict(source_observable.get("metadata") or {}),
                "source_observable": source_observable["name"],
                "source_series": selected_series["label"],
                "axis": "frequency",
                "preprocessing": "mean_subtracted",
            },
        },
        "sample_count": sample_count,
        "frequency_resolution": float(1.0 / (sample_count * dt)),
        "dominant_frequency": dominant_frequency,
        "source_series_label": str(selected_series["label"]),
    }


def _infer_uniform_step(times: list[float]) -> float | None:
    if len(times) < 2:
        return None
    dt = times[1] - times[0]
    if dt <= 0.0:
        return None
    for index in range(2, len(times)):
        step = times[index] - times[index - 1]
        if abs(step - dt) > 1e-8:
            return None
    return dt


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
