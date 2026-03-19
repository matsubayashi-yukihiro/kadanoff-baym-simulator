from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.schemas import (
    ArtifactRef,
    DecisionNoteCreate,
    DecisionNoteRecord,
    EvidenceBundleCreate,
    EvidenceBundleRecord,
    RunResearchMetadata,
    RunSummary,
    StudyCreate,
    StudyRecord,
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
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        bundle.created_at.isoformat(),
                        bundle.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_id not found") from exc
        return bundle

    def list_evidence_bundles(self, *, study_id: str | None = None) -> list[EvidenceBundleRecord]:
        params: list[Any] = []
        where_clause = ""
        if study_id is not None:
            where_clause = "WHERE study_id = ?"
            params.append(study_id)

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
                CREATE TABLE IF NOT EXISTS evidence_bundles (
                    bundle_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    claim_candidate TEXT NOT NULL,
                    artifact_refs_json TEXT NOT NULL,
                    analysis_refs_json TEXT NOT NULL,
                    validation_scope TEXT,
                    reproduction_recipe TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_study_id ON runs(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_decision_notes_study_id ON decision_notes(study_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_evidence_bundles_study_id ON evidence_bundles(study_id)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

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
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def _loads_json_list(value: str) -> list[Any]:
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)
