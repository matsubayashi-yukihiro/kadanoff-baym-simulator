from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StudyStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RunRole(str, Enum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"
    CONTROL = "control"
    NUMERICAL_CHECK = "numerical_check"


class ResearchValidationStatus(str, Enum):
    UNCHECKED = "unchecked"
    SCREENING = "screening"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ArtifactLifecycleState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparisonKind(str, Enum):
    PHYSICS_HYPOTHESIS = "physics_hypothesis"
    NUMERICAL_VALIDATION = "numerical_validation"
    REGRESSION = "regression"


class ParameterKind(str, Enum):
    PHYSICS = "physics"
    NUMERICAL = "numerical"
    ANALYSIS = "analysis"


class ArtifactSourceKind(str, Enum):
    RUN = "run"
    JOB_GROUP = "job_group"
    SWEEP = "sweep"
    ANALYSIS = "analysis"


class DecisionNoteKind(str, Enum):
    OBSERVATION = "observation"
    FAILURE = "failure"
    DECISION = "decision"
    TODO = "todo"


class DerivedAnalysisSourceKind(str, Enum):
    RUN = "run"
    JOB_GROUP = "job_group"
    SWEEP = "sweep"


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_kind: ArtifactSourceKind
    artifact_id: str


class RunResearchMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str | None = None
    run_role: RunRole | None = None
    validation_status: ResearchValidationStatus = ResearchValidationStatus.UNCHECKED
    failure_tags: list[str] = Field(default_factory=list)
    group_id: str | None = None
    sweep_id: str | None = None
    variant_label: str | None = None
    preset_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    config_hash: str | None = None
    code_version: str | None = None
    storage_uri: str | None = None


class RunResearchMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str | None = None
    run_role: RunRole | None = None
    validation_status: ResearchValidationStatus | None = None
    failure_tags: list[str] | None = None
    group_id: str | None = None
    sweep_id: str | None = None
    variant_label: str | None = None
    preset_id: str | None = None
    tags: list[str] | None = None
    code_version: str | None = None


class StudyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    question: str
    baseline_preset_id: str | None = None
    target_observables: list[str] = Field(default_factory=list)
    primary_surfaces: list[str] = Field(default_factory=list)
    acceptance_checks: list[str] = Field(default_factory=list)
    status: StudyStatus = StudyStatus.PLANNING
    notes_on_scope: str | None = None


class StudyRecord(StudyCreate):
    study_id: str
    created_at: datetime
    updated_at: datetime


class JobGroupVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    description: str | None = None
    config_patch: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None


class JobGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    name: str
    comparison_kind: ComparisonKind
    baseline_run_id: str | None = None
    base_config: dict[str, Any] = Field(default_factory=dict)
    variants: list[JobGroupVariant] = Field(default_factory=list)
    child_run_ids: list[str] = Field(default_factory=list)


class JobGroupRecord(JobGroupCreate):
    group_id: str
    state: ArtifactLifecycleState
    created_at: datetime
    updated_at: datetime


ScalarParameterValue = str | int | float | bool


class SweepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    name: str
    parameter_kind: ParameterKind
    parameter_path: str
    parameter_label: str
    values: list[ScalarParameterValue] = Field(default_factory=list)
    baseline_value: ScalarParameterValue | None = None
    fixed_axes: dict[str, Any] = Field(default_factory=dict)
    child_run_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_child_run_alignment(self) -> "SweepCreate":
        if self.child_run_ids and len(self.child_run_ids) != len(self.values):
            raise ValueError("child_run_ids length must match values length for sweep artifacts")
        return self


class SweepRecord(SweepCreate):
    sweep_id: str
    state: ArtifactLifecycleState
    created_at: datetime
    updated_at: datetime


class DecisionNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    source_kind: ArtifactSourceKind
    source_id: str
    note_kind: DecisionNoteKind
    body: str
    tags: list[str] = Field(default_factory=list)


class DecisionNoteRecord(DecisionNoteCreate):
    note_id: str
    created_at: datetime


class EvidenceBundleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    title: str
    claim_candidate: str
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    analysis_refs: list[str] = Field(default_factory=list)
    validation_scope: str | None = None
    reproduction_recipe: str | None = None


class EvidenceBundleRecord(EvidenceBundleCreate):
    bundle_id: str
    created_at: datetime
    updated_at: datetime


class DerivedAnalysisArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    source_kind: DerivedAnalysisSourceKind
    source_id: str
    analysis_type: str
    analysis_version: str = "v1"
    cache_key: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: ArtifactLifecycleState = ArtifactLifecycleState.QUEUED
    input_surface_ids: list[str] = Field(default_factory=list)
    result_metadata: dict[str, Any] = Field(default_factory=dict)
    data_refs: list[str] = Field(default_factory=list)
    supports_bundle_ids: list[str] = Field(default_factory=list)


class DerivedAnalysisArtifactRecord(DerivedAnalysisArtifactCreate):
    analysis_id: str
    created_at: datetime
    updated_at: datetime
