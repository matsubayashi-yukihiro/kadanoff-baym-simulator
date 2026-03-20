from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.schemas import (
    ArtifactLifecycleState,
    ArtifactRef,
    DecisionNoteCreate,
    DecisionNoteRecord,
    DerivedAnalysisArtifactCreate,
    DerivedAnalysisArtifactRecord,
    DerivedAnalysisSourceKind,
    EvidenceBundleCreate,
    EvidenceBundleRecord,
    JobGroupCreate,
    JobGroupRecord,
    JobGroupVariant,
    RunResearchMetadata,
    RunSummary,
    StudyCreate,
    StudyRecord,
    SweepCreate,
    SweepRecord,
)


class ExperimentRegistry:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def list_runs(self) -> list[RunSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT summary_json
                FROM runs
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [RunSummary.model_validate_json(row["summary_json"]) for row in rows]

    def get_run_metadata(self, run_id: str) -> RunResearchMetadata:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT research_metadata_json
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(run_id)
        return RunResearchMetadata.model_validate_json(row["research_metadata_json"])

    def upsert_run(self, summary: RunSummary) -> None:
        research_metadata = summary.research_metadata.model_dump(mode="json")
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO runs (
                        run_id,
                        name,
                        solver,
                        state,
                        created_at,
                        updated_at,
                        summary_json,
                        research_metadata_json,
                        study_id,
                        run_role,
                        validation_status,
                        group_id,
                        sweep_id,
                        variant_label,
                        preset_id,
                        config_hash,
                        code_version,
                        storage_uri
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        name = excluded.name,
                        solver = excluded.solver,
                        state = excluded.state,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        summary_json = excluded.summary_json,
                        research_metadata_json = excluded.research_metadata_json,
                        study_id = excluded.study_id,
                        run_role = excluded.run_role,
                        validation_status = excluded.validation_status,
                        group_id = excluded.group_id,
                        sweep_id = excluded.sweep_id,
                        variant_label = excluded.variant_label,
                        preset_id = excluded.preset_id,
                        config_hash = excluded.config_hash,
                        code_version = excluded.code_version,
                        storage_uri = excluded.storage_uri
                    """,
                    (
                        summary.run_id,
                        summary.name,
                        summary.solver,
                        summary.state.value,
                        summary.created_at.isoformat(),
                        summary.updated_at.isoformat(),
                        summary.model_dump_json(),
                        summary.research_metadata.model_dump_json(),
                        research_metadata["study_id"],
                        research_metadata["run_role"],
                        research_metadata["validation_status"],
                        research_metadata["group_id"],
                        research_metadata["sweep_id"],
                        research_metadata["variant_label"],
                        research_metadata["preset_id"],
                        research_metadata["config_hash"],
                        research_metadata["code_version"],
                        research_metadata["storage_uri"],
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_id not found") from exc

    def create_study(self, payload: StudyCreate) -> StudyRecord:
        now = _utcnow()
        study = StudyRecord(
            study_id=uuid4().hex,
            created_at=now,
            updated_at=now,
            **payload.model_dump(mode="json"),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO studies (
                    study_id,
                    title,
                    question,
                    baseline_preset_id,
                    target_observables_json,
                    primary_surfaces_json,
                    acceptance_checks_json,
                    status,
                    notes_on_scope,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    study.study_id,
                    study.title,
                    study.question,
                    study.baseline_preset_id,
                    json.dumps(study.target_observables),
                    json.dumps(study.primary_surfaces),
                    json.dumps(study.acceptance_checks),
                    study.status.value,
                    study.notes_on_scope,
                    study.created_at.isoformat(),
                    study.updated_at.isoformat(),
                ),
            )
        return study

    def list_studies(self) -> list[StudyRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM studies
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._study_from_row(row) for row in rows]

    def get_study(self, study_id: str) -> StudyRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM studies
                WHERE study_id = ?
                """,
                (study_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(study_id)
        return self._study_from_row(row)

    def create_job_group(self, payload: JobGroupCreate) -> JobGroupRecord:
        now = _utcnow()
        group_id = uuid4().hex
        with self._connect() as connection:
            state = _aggregate_artifact_state(self._fetch_run_states(connection, payload.child_run_ids))
            try:
                connection.execute(
                    """
                    INSERT INTO job_groups (
                        group_id,
                        study_id,
                        name,
                        comparison_kind,
                        baseline_run_id,
                        base_config_json,
                        variants_json,
                        state,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_id,
                        payload.study_id,
                        payload.name,
                        payload.comparison_kind.value,
                        payload.baseline_run_id,
                        json.dumps(payload.base_config),
                        json.dumps([variant.model_dump(mode="json") for variant in payload.variants]),
                        state.value,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                self._replace_job_group_runs(connection, group_id=group_id, child_run_ids=payload.child_run_ids)
            except sqlite3.IntegrityError as exc:
                raise ValueError("study_id or run_id not found") from exc
        return self.get_job_group(group_id)

    def list_job_groups(self, *, study_id: str | None = None) -> list[JobGroupRecord]:
        params: list[Any] = []
        where_clause = ""
        if study_id is not None:
            where_clause = "WHERE study_id = ?"
            params.append(study_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM job_groups
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
            return [self._job_group_from_row(connection, row) for row in rows]

    def get_job_group(self, group_id: str) -> JobGroupRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM job_groups
                WHERE group_id = ?
                """,
                (group_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(group_id)
            return self._job_group_from_row(connection, row)

    def create_sweep(self, payload: SweepCreate) -> SweepRecord:
        now = _utcnow()
        sweep_id = uuid4().hex
        with self._connect() as connection:
            state = _aggregate_artifact_state(self._fetch_run_states(connection, payload.child_run_ids))
            try:
                connection.execute(
                    """
                    INSERT INTO sweeps (
                        sweep_id,
                        study_id,
                        name,
                        parameter_kind,
                        parameter_path,
                        parameter_label,
                        values_json,
                        baseline_value_json,
                        fixed_axes_json,
                        state,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sweep_id,
                        payload.study_id,
                        payload.name,
                        payload.parameter_kind.value,
                        payload.parameter_path,
                        payload.parameter_label,
                        json.dumps(payload.values),
                        json.dumps(payload.baseline_value),
                        json.dumps(payload.fixed_axes),
                        state.value,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                self._replace_sweep_runs(
                    connection,
                    sweep_id=sweep_id,
                    child_run_ids=payload.child_run_ids,
                    values=payload.values,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("study_id or run_id not found") from exc
        return self.get_sweep(sweep_id)

    def list_sweeps(self, *, study_id: str | None = None) -> list[SweepRecord]:
        params: list[Any] = []
        where_clause = ""
        if study_id is not None:
            where_clause = "WHERE study_id = ?"
            params.append(study_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM sweeps
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
            return [self._sweep_from_row(connection, row) for row in rows]

    def get_sweep(self, sweep_id: str) -> SweepRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM sweeps
                WHERE sweep_id = ?
                """,
                (sweep_id,),
            ).fetchone()
            if row is None:
                raise FileNotFoundError(sweep_id)
            return self._sweep_from_row(connection, row)

    def create_decision_note(self, payload: DecisionNoteCreate) -> DecisionNoteRecord:
        note = DecisionNoteRecord(
            note_id=uuid4().hex,
            created_at=_utcnow(),
            **payload.model_dump(mode="json"),
        )
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO decision_notes (
                        note_id,
                        study_id,
                        source_kind,
                        source_id,
                        note_kind,
                        body,
                        tags_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        note.note_id,
                        note.study_id,
                        note.source_kind.value,
                        note.source_id,
                        note.note_kind.value,
                        note.body,
                        json.dumps(note.tags),
                        note.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_id not found") from exc
        return note

    def list_decision_notes(
        self,
        *,
        study_id: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> list[DecisionNoteRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if study_id is not None:
            clauses.append("study_id = ?")
            params.append(study_id)
        if source_kind is not None:
            clauses.append("source_kind = ?")
            params.append(source_kind)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)

        where_clause = ""
        if clauses:
            where_clause = "WHERE " + " AND ".join(clauses)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM decision_notes
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [self._decision_note_from_row(row) for row in rows]

    def get_decision_note(self, note_id: str) -> DecisionNoteRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM decision_notes
                WHERE note_id = ?
                """,
                (note_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(note_id)
        return self._decision_note_from_row(row)

    def create_derived_analysis(self, payload: DerivedAnalysisArtifactCreate) -> DerivedAnalysisArtifactRecord:
        now = _utcnow()
        analysis = DerivedAnalysisArtifactRecord(
            analysis_id=uuid4().hex,
            created_at=now,
            updated_at=now,
            **payload.model_dump(mode="json"),
        )
        with self._connect() as connection:
            self._ensure_analysis_source_exists(connection, payload.source_kind, payload.source_id)
            try:
                connection.execute(
                    """
                    INSERT INTO derived_analyses (
                        analysis_id,
                        study_id,
                        source_kind,
                        source_id,
                        analysis_type,
                        analysis_version,
                        cache_key,
                        status,
                        parameters_json,
                        input_surface_ids_json,
                        result_metadata_json,
                        data_refs_json,
                        supports_bundle_ids_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis.analysis_id,
                        analysis.study_id,
                        analysis.source_kind.value,
                        analysis.source_id,
                        analysis.analysis_type,
                        analysis.analysis_version,
                        analysis.cache_key,
                        analysis.status.value,
                        json.dumps(analysis.parameters),
                        json.dumps(analysis.input_surface_ids),
                        json.dumps(analysis.result_metadata),
                        json.dumps(analysis.data_refs),
                        json.dumps(analysis.supports_bundle_ids),
                        analysis.created_at.isoformat(),
                        analysis.updated_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("study_id not found") from exc
        return analysis

    def list_derived_analyses(
        self,
        *,
        study_id: str | None = None,
        source_kind: DerivedAnalysisSourceKind | None = None,
        source_id: str | None = None,
    ) -> list[DerivedAnalysisArtifactRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if study_id is not None:
            clauses.append("study_id = ?")
            params.append(study_id)
        if source_kind is not None:
            clauses.append("source_kind = ?")
            params.append(source_kind.value)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)

        where_clause = ""
        if clauses:
            where_clause = "WHERE " + " AND ".join(clauses)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM derived_analyses
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [self._derived_analysis_from_row(row) for row in rows]

    def get_derived_analysis(self, analysis_id: str) -> DerivedAnalysisArtifactRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM derived_analyses
                WHERE analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(analysis_id)
        return self._derived_analysis_from_row(row)

    def update_derived_analysis(self, analysis: DerivedAnalysisArtifactRecord) -> DerivedAnalysisArtifactRecord:
        updated = analysis.model_copy(update={"updated_at": _utcnow()})
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE derived_analyses
                SET status = ?,
                    parameters_json = ?,
                    input_surface_ids_json = ?,
                    result_metadata_json = ?,
                    data_refs_json = ?,
                    supports_bundle_ids_json = ?,
                    updated_at = ?
                WHERE analysis_id = ?
                """,
                (
                    updated.status.value,
                    json.dumps(updated.parameters),
                    json.dumps(updated.input_surface_ids),
                    json.dumps(updated.result_metadata),
                    json.dumps(updated.data_refs),
                    json.dumps(updated.supports_bundle_ids),
                    updated.updated_at.isoformat(),
                    updated.analysis_id,
                ),
            )
        if cursor.rowcount == 0:
            raise FileNotFoundError(updated.analysis_id)
        return updated

    def create_evidence_bundle(self, payload: EvidenceBundleCreate) -> EvidenceBundleRecord:
        now = _utcnow()
        bundle = EvidenceBundleRecord(
            bundle_id=uuid4().hex,
            created_at=now,
            updated_at=now,
            **payload.model_dump(mode="json"),
        )
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO evidence_bundles (
                        bundle_id,
                        study_id,
                        title,
                        claim_candidate,
                        artifact_refs_json,
                        analysis_refs_json,
                        validation_scope,
                        reproduction_recipe,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bundle.bundle_id,
                        bundle.study_id,
                        bundle.title,
                        bundle.claim_candidate,
                        json.dumps([ref.model_dump(mode="json") for ref in bundle.artifact_refs]),
                        json.dumps(bundle.analysis_refs),
                        bundle.validation_scope,
                        bundle.reproduction_recipe,
                        bundle.status.value,
                        bundle.created_at.isoformat(),
                        bundle.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_id not found") from exc
        return bundle

    def list_evidence_bundles(
        self,
        *,
        study_id: str | None = None,
        status: EvidenceBundleStatus | None = None,
    ) -> list[EvidenceBundleRecord]:
        params: list[Any] = []
        filters: list[str] = []
        if study_id is not None:
            filters.append("study_id = ?")
            params.append(study_id)
        if status is not None:
            filters.append("status = ?")
            params.append(status.value)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM evidence_bundles
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [self._evidence_bundle_from_row(row) for row in rows]

    def get_evidence_bundle(self, bundle_id: str) -> EvidenceBundleRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM evidence_bundles
                WHERE bundle_id = ?
                """,
                (bundle_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(bundle_id)
        return self._evidence_bundle_from_row(row)

    def update_evidence_bundle(self, bundle: EvidenceBundleRecord) -> EvidenceBundleRecord:
        updated = bundle.model_copy(update={"updated_at": _utcnow()})
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE evidence_bundles
                SET title = ?,
                    claim_candidate = ?,
                    artifact_refs_json = ?,
                    analysis_refs_json = ?,
                    validation_scope = ?,
                    reproduction_recipe = ?,
                    status = ?,
                    updated_at = ?
                WHERE bundle_id = ?
                """,
                (
                    updated.title,
                    updated.claim_candidate,
                    json.dumps([ref.model_dump(mode="json") for ref in updated.artifact_refs]),
                    json.dumps(updated.analysis_refs),
                    updated.validation_scope,
                    updated.reproduction_recipe,
                    updated.status.value,
                    updated.updated_at.isoformat(),
                    updated.bundle_id,
                ),
            )
        if cursor.rowcount == 0:
            raise FileNotFoundError(updated.bundle_id)
        return updated

    def refresh_parent_states_for_run(self, run_id: str) -> None:
        with self._connect() as connection:
            job_group_ids = connection.execute(
                """
                SELECT DISTINCT group_id
                FROM job_group_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchall()
            for row in job_group_ids:
                self._refresh_job_group_state(connection, row["group_id"])

            sweep_ids = connection.execute(
                """
                SELECT DISTINCT sweep_id
                FROM sweep_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchall()
            for row in sweep_ids:
                self._refresh_sweep_state(connection, row["sweep_id"])

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS studies (
                    study_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    question TEXT NOT NULL,
                    baseline_preset_id TEXT,
                    target_observables_json TEXT NOT NULL,
                    primary_surfaces_json TEXT NOT NULL,
                    acceptance_checks_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes_on_scope TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT,
                    solver TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    research_metadata_json TEXT NOT NULL,
                    study_id TEXT REFERENCES studies(study_id) ON DELETE SET NULL,
                    run_role TEXT,
                    validation_status TEXT NOT NULL,
                    group_id TEXT,
                    sweep_id TEXT,
                    variant_label TEXT,
                    preset_id TEXT,
                    config_hash TEXT,
                    code_version TEXT,
                    storage_uri TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_groups (
                    group_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    comparison_kind TEXT NOT NULL,
                    baseline_run_id TEXT REFERENCES runs(run_id) ON DELETE SET NULL,
                    base_config_json TEXT NOT NULL,
                    variants_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_group_runs (
                    group_id TEXT NOT NULL REFERENCES job_groups(group_id) ON DELETE CASCADE,
                    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    PRIMARY KEY (group_id, run_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sweeps (
                    sweep_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    parameter_kind TEXT NOT NULL,
                    parameter_path TEXT NOT NULL,
                    parameter_label TEXT NOT NULL,
                    values_json TEXT NOT NULL,
                    baseline_value_json TEXT NOT NULL,
                    fixed_axes_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sweep_runs (
                    sweep_id TEXT NOT NULL REFERENCES sweeps(sweep_id) ON DELETE CASCADE,
                    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    parameter_value_json TEXT NOT NULL,
                    PRIMARY KEY (sweep_id, run_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_notes (
                    note_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE CASCADE,
                    source_kind TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    note_kind TEXT NOT NULL,
                    body TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS derived_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE CASCADE,
                    source_kind TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    analysis_version TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    input_surface_ids_json TEXT NOT NULL,
                    result_metadata_json TEXT NOT NULL,
                    data_refs_json TEXT NOT NULL,
                    supports_bundle_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_bundles (
                    bundle_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    claim_candidate TEXT NOT NULL,
                    artifact_refs_json TEXT NOT NULL,
                    analysis_refs_json TEXT NOT NULL,
                    validation_scope TEXT,
                    reproduction_recipe TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            evidence_bundle_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(evidence_bundles)").fetchall()
            }
            if "status" not in evidence_bundle_columns:
                connection.execute("ALTER TABLE evidence_bundles ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_study_id ON runs(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_job_groups_study_id ON job_groups(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_job_group_runs_run_id ON job_group_runs(run_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_sweeps_study_id ON sweeps(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_sweep_runs_run_id ON sweep_runs(run_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_decision_notes_study_id ON decision_notes(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_derived_analyses_study_id ON derived_analyses(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_derived_analyses_source ON derived_analyses(source_kind, source_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_evidence_bundles_study_id ON evidence_bundles(study_id)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _replace_job_group_runs(
        self,
        connection: sqlite3.Connection,
        *,
        group_id: str,
        child_run_ids: list[str],
    ) -> None:
        connection.execute("DELETE FROM job_group_runs WHERE group_id = ?", (group_id,))
        if not child_run_ids:
            return
        connection.executemany(
            """
            INSERT INTO job_group_runs (group_id, run_id, ordinal)
            VALUES (?, ?, ?)
            """,
            [(group_id, run_id, ordinal) for ordinal, run_id in enumerate(child_run_ids)],
        )

    def _replace_sweep_runs(
        self,
        connection: sqlite3.Connection,
        *,
        sweep_id: str,
        child_run_ids: list[str],
        values: list[Any],
    ) -> None:
        connection.execute("DELETE FROM sweep_runs WHERE sweep_id = ?", (sweep_id,))
        if not child_run_ids:
            return
        connection.executemany(
            """
            INSERT INTO sweep_runs (sweep_id, run_id, ordinal, parameter_value_json)
            VALUES (?, ?, ?, ?)
            """,
            [
                (sweep_id, run_id, ordinal, json.dumps(values[ordinal]))
                for ordinal, run_id in enumerate(child_run_ids)
            ],
        )

    def _refresh_job_group_state(self, connection: sqlite3.Connection, group_id: str) -> None:
        child_run_ids = self._fetch_child_run_ids(connection, table="job_group_runs", artifact_id_column="group_id", artifact_id=group_id)
        new_state = _aggregate_artifact_state(self._fetch_run_states(connection, child_run_ids))
        connection.execute(
            """
            UPDATE job_groups
            SET state = ?, updated_at = ?
            WHERE group_id = ?
            """,
            (new_state.value, _utcnow().isoformat(), group_id),
        )

    def _refresh_sweep_state(self, connection: sqlite3.Connection, sweep_id: str) -> None:
        child_run_ids = self._fetch_child_run_ids(connection, table="sweep_runs", artifact_id_column="sweep_id", artifact_id=sweep_id)
        new_state = _aggregate_artifact_state(self._fetch_run_states(connection, child_run_ids))
        connection.execute(
            """
            UPDATE sweeps
            SET state = ?, updated_at = ?
            WHERE sweep_id = ?
            """,
            (new_state.value, _utcnow().isoformat(), sweep_id),
        )

    def _fetch_child_run_ids(
        self,
        connection: sqlite3.Connection,
        *,
        table: str,
        artifact_id_column: str,
        artifact_id: str,
    ) -> list[str]:
        rows = connection.execute(
            f"""
            SELECT run_id
            FROM {table}
            WHERE {artifact_id_column} = ?
            ORDER BY ordinal ASC
            """,
            (artifact_id,),
        ).fetchall()
        return [row["run_id"] for row in rows]

    def _fetch_run_states(self, connection: sqlite3.Connection, run_ids: list[str]) -> list[ArtifactLifecycleState]:
        if not run_ids:
            return []
        rows = connection.execute(
            f"""
            SELECT state
            FROM runs
            WHERE run_id IN ({",".join("?" for _ in run_ids)})
            """,
            run_ids,
        ).fetchall()
        return [ArtifactLifecycleState(row["state"]) for row in rows]

    def _ensure_analysis_source_exists(
        self,
        connection: sqlite3.Connection,
        source_kind: DerivedAnalysisSourceKind,
        source_id: str,
    ) -> None:
        table = {
            DerivedAnalysisSourceKind.RUN: "runs",
            DerivedAnalysisSourceKind.JOB_GROUP: "job_groups",
            DerivedAnalysisSourceKind.SWEEP: "sweeps",
        }[source_kind]
        id_column = {
            DerivedAnalysisSourceKind.RUN: "run_id",
            DerivedAnalysisSourceKind.JOB_GROUP: "group_id",
            DerivedAnalysisSourceKind.SWEEP: "sweep_id",
        }[source_kind]
        row = connection.execute(
            f"""
            SELECT 1
            FROM {table}
            WHERE {id_column} = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"{source_kind.value} source_id not found")

    @staticmethod
    def _study_from_row(row: sqlite3.Row) -> StudyRecord:
        return StudyRecord(
            study_id=row["study_id"],
            title=row["title"],
            question=row["question"],
            baseline_preset_id=row["baseline_preset_id"],
            target_observables=_loads_json_list(row["target_observables_json"]),
            primary_surfaces=_loads_json_list(row["primary_surfaces_json"]),
            acceptance_checks=_loads_json_list(row["acceptance_checks_json"]),
            status=row["status"],
            notes_on_scope=row["notes_on_scope"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _job_group_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> JobGroupRecord:
        child_run_ids = self._fetch_child_run_ids(
            connection,
            table="job_group_runs",
            artifact_id_column="group_id",
            artifact_id=row["group_id"],
        )
        return JobGroupRecord(
            group_id=row["group_id"],
            study_id=row["study_id"],
            name=row["name"],
            comparison_kind=row["comparison_kind"],
            baseline_run_id=row["baseline_run_id"],
            base_config=_loads_json_object(row["base_config_json"]),
            variants=[JobGroupVariant.model_validate(item) for item in json.loads(row["variants_json"])],
            child_run_ids=child_run_ids,
            state=row["state"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _sweep_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> SweepRecord:
        child_run_ids = self._fetch_child_run_ids(
            connection,
            table="sweep_runs",
            artifact_id_column="sweep_id",
            artifact_id=row["sweep_id"],
        )
        return SweepRecord(
            sweep_id=row["sweep_id"],
            study_id=row["study_id"],
            name=row["name"],
            parameter_kind=row["parameter_kind"],
            parameter_path=row["parameter_path"],
            parameter_label=row["parameter_label"],
            values=_loads_json_list(row["values_json"]),
            baseline_value=json.loads(row["baseline_value_json"]),
            fixed_axes=_loads_json_object(row["fixed_axes_json"]),
            child_run_ids=child_run_ids,
            state=row["state"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _decision_note_from_row(row: sqlite3.Row) -> DecisionNoteRecord:
        return DecisionNoteRecord(
            note_id=row["note_id"],
            study_id=row["study_id"],
            source_kind=row["source_kind"],
            source_id=row["source_id"],
            note_kind=row["note_kind"],
            body=row["body"],
            tags=_loads_json_list(row["tags_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _derived_analysis_from_row(row: sqlite3.Row) -> DerivedAnalysisArtifactRecord:
        return DerivedAnalysisArtifactRecord(
            analysis_id=row["analysis_id"],
            study_id=row["study_id"],
            source_kind=row["source_kind"],
            source_id=row["source_id"],
            analysis_type=row["analysis_type"],
            analysis_version=row["analysis_version"],
            cache_key=row["cache_key"],
            status=row["status"],
            parameters=_loads_json_object(row["parameters_json"]),
            input_surface_ids=_loads_json_list(row["input_surface_ids_json"]),
            result_metadata=_loads_json_object(row["result_metadata_json"]),
            data_refs=_loads_json_list(row["data_refs_json"]),
            supports_bundle_ids=_loads_json_list(row["supports_bundle_ids_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _evidence_bundle_from_row(row: sqlite3.Row) -> EvidenceBundleRecord:
        return EvidenceBundleRecord(
            bundle_id=row["bundle_id"],
            study_id=row["study_id"],
            title=row["title"],
            claim_candidate=row["claim_candidate"],
            artifact_refs=[ArtifactRef.model_validate(item) for item in json.loads(row["artifact_refs_json"])],
            analysis_refs=_loads_json_list(row["analysis_refs_json"]),
            validation_scope=row["validation_scope"],
            reproduction_recipe=row["reproduction_recipe"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def _loads_json_list(value: str) -> list[Any]:
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []


def _loads_json_object(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _aggregate_artifact_state(states: list[ArtifactLifecycleState]) -> ArtifactLifecycleState:
    state_set = set(states)
    if not state_set:
        return ArtifactLifecycleState.QUEUED
    if ArtifactLifecycleState.RUNNING in state_set:
        return ArtifactLifecycleState.RUNNING
    if ArtifactLifecycleState.QUEUED in state_set:
        return ArtifactLifecycleState.QUEUED
    if ArtifactLifecycleState.FAILED in state_set:
        return ArtifactLifecycleState.FAILED
    if state_set == {ArtifactLifecycleState.SUCCEEDED}:
        return ArtifactLifecycleState.SUCCEEDED
    return ArtifactLifecycleState.CANCELLED


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)
