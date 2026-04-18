from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_state_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        root = Path(local_appdata)
    else:
        root = Path.home() / "AppData" / "Local"

    state_root = root / "RiftReader" / "GameDebugScannerHub"
    state_root.mkdir(parents=True, exist_ok=True)
    (state_root / "sessions").mkdir(parents=True, exist_ok=True)
    (state_root / "recovery-packages").mkdir(parents=True, exist_ok=True)
    return state_root


def _to_json(value: Any) -> str | None:
    if value is None:
        return None

    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return json.dumps({"repr": repr(value)}, ensure_ascii=False, sort_keys=True)


def _from_json(value: str | None) -> Any:
    if not value:
        return None

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(0.99, round(float(value), 4)))


def _anchor_distance_bonus(anchor_distance: Any) -> float:
    if not isinstance(anchor_distance, (int, float)):
        return 0.0

    distance = abs(int(anchor_distance))
    if distance <= 0:
        return 0.12
    if distance <= 0x20:
        return 0.10
    if distance <= 0x100:
        return 0.08
    if distance <= 0x400:
        return 0.05
    if distance <= 0x1000:
        return 0.03
    return 0.0


def _compute_candidate_confidence(
    base_confidence: float,
    *,
    evidence_count: int,
    metadata: dict[str, Any] | None,
    status: str,
) -> float:
    score = float(base_confidence)
    score += min(0.18, max(evidence_count - 1, 0) * 0.03)

    if status in {"confirmed", "promoted", "resolved"}:
        score += 0.05
    if metadata:
        score += _anchor_distance_bonus(metadata.get("anchor_distance"))
        if metadata.get("module_name") and metadata.get("module_rva") is not None:
            score += 0.03
        if metadata.get("resolved_via") == "ct-import":
            score += 0.02
        if metadata.get("scan_scope") == "anchor-neighborhood":
            score += 0.03

    if status == "stale":
        score = min(score, 0.35)
    elif status == "broken":
        score = min(score, 0.20)

    return _clamp_confidence(score)


@dataclass(slots=True)
class CandidateRecord:
    candidate_id: int
    canonical_key: str
    kind: str
    label: str
    status: str
    confidence: float
    value_type: str | None
    module_name: str | None
    module_rva: int | None
    absolute_address: int | None
    source_kind: str | None
    notes: str | None
    artifact_path: str | None
    metadata_json: str | None
    first_seen_at: str
    last_seen_at: str
    last_verified_at: str | None
    evidence_count: int
    last_game_build: str | None

    @property
    def address_hex(self) -> str:
        if self.absolute_address is None:
            return ""
        return f"0x{self.absolute_address:X}"

    @property
    def metadata(self) -> dict[str, Any]:
        payload = _from_json(self.metadata_json)
        return payload if isinstance(payload, dict) else {}


@dataclass(slots=True)
class CandidateEvidenceRecord:
    evidence_id: int
    candidate_id: int
    session_id: int | None
    created_at: str
    event_kind: str
    summary: str
    metadata_json: str | None

    @property
    def metadata(self) -> dict[str, Any]:
        payload = _from_json(self.metadata_json)
        return payload if isinstance(payload, dict) else {}


@dataclass(slots=True)
class EventRecord:
    event_id: int
    session_id: int | None
    created_at: str
    kind: str
    summary: str
    metadata_json: str | None

    @property
    def metadata(self) -> dict[str, Any]:
        payload = _from_json(self.metadata_json)
        return payload if isinstance(payload, dict) else {}


@dataclass(slots=True)
class SessionRecord:
    session_id: int
    started_at: str
    ended_at: str | None
    repo_root: str | None
    scanner_version: str | None
    notes: str | None


@dataclass(slots=True)
class ImportRecord:
    import_id: int
    source_path: str
    label: str
    imported_at: str
    entry_count: int
    warning_count: int
    notes: str | None
    metadata_json: str | None

    @property
    def metadata(self) -> dict[str, Any]:
        payload = _from_json(self.metadata_json)
        return payload if isinstance(payload, dict) else {}


@dataclass(slots=True)
class ImportEntryRecord:
    entry_id: int
    import_id: int
    import_key: str
    label: str
    group_path: str | None
    kind: str
    status: str
    confidence: float
    value_type: str | None
    address_expression: str | None
    module_name: str | None
    module_rva: int | None
    resolved_address: int | None
    offsets_json: str | None
    notes: str | None
    metadata_json: str | None
    last_resolved_at: str | None
    last_error: str | None
    promoted_candidate_id: int | None

    @property
    def offsets(self) -> list[int]:
        payload = _from_json(self.offsets_json)
        if isinstance(payload, list):
            return [int(value) for value in payload]
        return []

    @property
    def metadata(self) -> dict[str, Any]:
        payload = _from_json(self.metadata_json)
        return payload if isinstance(payload, dict) else {}

    @property
    def resolved_address_hex(self) -> str:
        if self.resolved_address is None:
            return ""
        return f"0x{self.resolved_address:X}"


class DiscoveryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.state_root = default_state_root() if db_path is None else db_path.resolve().parent
        self.db_path = (db_path or (default_state_root() / "hub.db")).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._session_id: int | None = None
        self._session_started_at: str | None = None
        self._initialize_schema()

    @property
    def session_id(self) -> int | None:
        return self._session_id

    @property
    def session_started_at(self) -> str | None:
        return self._session_started_at

    def _initialize_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                repo_root TEXT,
                scanner_version TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                value_json TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                summary TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_key TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                value_type TEXT,
                module_name TEXT,
                module_rva INTEGER,
                absolute_address INTEGER,
                source_kind TEXT,
                notes TEXT,
                artifact_path TEXT,
                metadata_json TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_verified_at TEXT,
                last_game_build TEXT
            );

            CREATE TABLE IF NOT EXISTS candidate_evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                session_id INTEGER,
                created_at TEXT NOT NULL,
                event_kind TEXT NOT NULL,
                summary TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id),
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS imports (
                import_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                entry_count INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS import_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id INTEGER NOT NULL,
                import_key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                group_path TEXT,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                value_type TEXT,
                address_expression TEXT,
                module_name TEXT,
                module_rva INTEGER,
                resolved_address INTEGER,
                offsets_json TEXT,
                notes TEXT,
                metadata_json TEXT,
                last_resolved_at TEXT,
                last_error TEXT,
                promoted_candidate_id INTEGER,
                FOREIGN KEY(import_id) REFERENCES imports(import_id),
                FOREIGN KEY(promoted_candidate_id) REFERENCES candidates(candidate_id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_session_created
            ON events(session_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_candidates_status_kind
            ON candidates(status, kind, source_kind);

            CREATE INDEX IF NOT EXISTS idx_candidate_evidence_candidate_created
            ON candidate_evidence(candidate_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_import_entries_import_status
            ON import_entries(import_id, status, kind);
            """
        )
        self._ensure_column("sessions", "notes", "TEXT")
        self.conn.commit()

    def _ensure_column(self, table_name: str, column_name: str, column_type: str) -> None:
        columns = {
            str(row["name"])
            for row in self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> CandidateRecord:
        return CandidateRecord(
            candidate_id=int(row["candidate_id"]),
            canonical_key=str(row["canonical_key"]),
            kind=str(row["kind"]),
            label=str(row["label"]),
            status=str(row["status"]),
            confidence=float(row["confidence"] or 0.0),
            value_type=row["value_type"],
            module_name=row["module_name"],
            module_rva=row["module_rva"],
            absolute_address=row["absolute_address"],
            source_kind=row["source_kind"],
            notes=row["notes"],
            artifact_path=row["artifact_path"],
            metadata_json=row["metadata_json"],
            first_seen_at=str(row["first_seen_at"]),
            last_seen_at=str(row["last_seen_at"]),
            last_verified_at=row["last_verified_at"],
            evidence_count=int(row["evidence_count"] or 0),
            last_game_build=row["last_game_build"],
        )

    @staticmethod
    def _row_to_evidence(row: sqlite3.Row) -> CandidateEvidenceRecord:
        return CandidateEvidenceRecord(
            evidence_id=int(row["evidence_id"]),
            candidate_id=int(row["candidate_id"]),
            session_id=row["session_id"],
            created_at=str(row["created_at"]),
            event_kind=str(row["event_kind"]),
            summary=str(row["summary"]),
            metadata_json=row["metadata_json"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            event_id=int(row["event_id"]),
            session_id=row["session_id"],
            created_at=str(row["created_at"]),
            kind=str(row["kind"]),
            summary=str(row["summary"]),
            metadata_json=row["metadata_json"],
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            session_id=int(row["session_id"]),
            started_at=str(row["started_at"]),
            ended_at=row["ended_at"],
            repo_root=row["repo_root"],
            scanner_version=row["scanner_version"],
            notes=row["notes"],
        )

    @staticmethod
    def _row_to_import(row: sqlite3.Row) -> ImportRecord:
        return ImportRecord(
            import_id=int(row["import_id"]),
            source_path=str(row["source_path"]),
            label=str(row["label"]),
            imported_at=str(row["imported_at"]),
            entry_count=int(row["entry_count"] or 0),
            warning_count=int(row["warning_count"] or 0),
            notes=row["notes"],
            metadata_json=row["metadata_json"],
        )

    @staticmethod
    def _row_to_import_entry(row: sqlite3.Row) -> ImportEntryRecord:
        return ImportEntryRecord(
            entry_id=int(row["entry_id"]),
            import_id=int(row["import_id"]),
            import_key=str(row["import_key"]),
            label=str(row["label"]),
            group_path=row["group_path"],
            kind=str(row["kind"]),
            status=str(row["status"]),
            confidence=float(row["confidence"] or 0.0),
            value_type=row["value_type"],
            address_expression=row["address_expression"],
            module_name=row["module_name"],
            module_rva=row["module_rva"],
            resolved_address=row["resolved_address"],
            offsets_json=row["offsets_json"],
            notes=row["notes"],
            metadata_json=row["metadata_json"],
            last_resolved_at=row["last_resolved_at"],
            last_error=row["last_error"],
            promoted_candidate_id=row["promoted_candidate_id"],
        )

    def open_session(self, *, repo_root: str | None = None, scanner_version: str | None = None) -> int:
        if self._session_id is not None:
            return self._session_id

        started_at = utc_now_iso()
        cursor = self.conn.execute(
            """
            INSERT INTO sessions (started_at, repo_root, scanner_version, notes)
            VALUES (?, ?, ?, ?)
            """,
            (started_at, repo_root, scanner_version, ""),
        )
        self.conn.commit()
        self._session_id = int(cursor.lastrowid)
        self._session_started_at = started_at
        return self._session_id

    def close(self) -> None:
        if self._session_id is not None:
            self.conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
                (utc_now_iso(), self._session_id),
            )
            self.conn.commit()
            self._session_id = None
            self._session_started_at = None

        self.conn.close()

    def get_session(self, session_id: int | None = None) -> SessionRecord | None:
        target_session_id = session_id or self._session_id
        if target_session_id is None:
            return None

        row = self.conn.execute(
            """
            SELECT session_id, started_at, ended_at, repo_root, scanner_version, notes
            FROM sessions
            WHERE session_id = ?
            """,
            (target_session_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def set_session_notes(self, notes: str) -> None:
        if self._session_id is None:
            return
        self.conn.execute(
            "UPDATE sessions SET notes = ? WHERE session_id = ?",
            (notes, self._session_id),
        )
        self.conn.commit()

    def get_session_notes(self, session_id: int | None = None) -> str:
        session = self.get_session(session_id)
        return (session.notes or "") if session else ""

    def set_setting(self, key: str, value: Any) -> None:
        now = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO settings (setting_key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, _to_json(value), now),
        )
        self.conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute(
            "SELECT value_json FROM settings WHERE setting_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        value = _from_json(row["value_json"])
        return default if value is None else value

    def add_event(self, kind: str, summary: str, metadata: Any = None) -> int:
        created_at = utc_now_iso()
        cursor = self.conn.execute(
            """
            INSERT INTO events (session_id, created_at, kind, summary, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (self._session_id, created_at, kind, summary, _to_json(metadata)),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def list_events(self, *, limit: int = 500, session_id: int | None = None) -> list[EventRecord]:
        session_filter = session_id or self._session_id
        query = """
            SELECT event_id, session_id, created_at, kind, summary, metadata_json
            FROM events
        """
        params: list[Any] = []
        if session_filter is not None:
            query += " WHERE session_id = ?"
            params.append(session_filter)
        query += " ORDER BY created_at DESC, event_id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_event(row) for row in rows]

    def upsert_candidate(
        self,
        *,
        canonical_key: str,
        kind: str,
        label: str,
        status: str = "candidate",
        confidence: float = 0.0,
        value_type: str | None = None,
        module_name: str | None = None,
        module_rva: int | None = None,
        absolute_address: int | None = None,
        source_kind: str | None = None,
        notes: str | None = None,
        artifact_path: str | None = None,
        metadata: Any = None,
        last_game_build: str | None = None,
        verified: bool = False,
        evidence_kind: str | None = None,
        evidence_summary: str | None = None,
        evidence_metadata: Any = None,
    ) -> int:
        now = utc_now_iso()
        metadata_payload = metadata if isinstance(metadata, dict) else {}
        if module_name and "module_name" not in metadata_payload:
            metadata_payload["module_name"] = module_name
        if module_rva is not None and "module_rva" not in metadata_payload:
            metadata_payload["module_rva"] = module_rva
        metadata_json = _to_json(metadata_payload or metadata)
        last_verified_at = now if verified else None

        self.conn.execute(
            """
            INSERT INTO candidates (
                canonical_key,
                kind,
                label,
                status,
                confidence,
                value_type,
                module_name,
                module_rva,
                absolute_address,
                source_kind,
                notes,
                artifact_path,
                metadata_json,
                first_seen_at,
                last_seen_at,
                last_verified_at,
                last_game_build
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_key) DO UPDATE SET
                kind = excluded.kind,
                label = excluded.label,
                status = excluded.status,
                confidence = excluded.confidence,
                value_type = COALESCE(excluded.value_type, candidates.value_type),
                module_name = COALESCE(excluded.module_name, candidates.module_name),
                module_rva = COALESCE(excluded.module_rva, candidates.module_rva),
                absolute_address = COALESCE(excluded.absolute_address, candidates.absolute_address),
                source_kind = COALESCE(excluded.source_kind, candidates.source_kind),
                notes = CASE
                    WHEN excluded.notes IS NULL OR excluded.notes = '' THEN candidates.notes
                    WHEN candidates.notes IS NULL OR candidates.notes = '' THEN excluded.notes
                    WHEN instr(candidates.notes, excluded.notes) > 0 THEN candidates.notes
                    ELSE candidates.notes || char(10) || excluded.notes
                END,
                artifact_path = COALESCE(excluded.artifact_path, candidates.artifact_path),
                metadata_json = COALESCE(excluded.metadata_json, candidates.metadata_json),
                last_seen_at = excluded.last_seen_at,
                last_verified_at = COALESCE(excluded.last_verified_at, candidates.last_verified_at),
                last_game_build = COALESCE(excluded.last_game_build, candidates.last_game_build)
            """,
            (
                canonical_key,
                kind,
                label,
                status,
                _clamp_confidence(confidence),
                value_type,
                module_name,
                module_rva,
                absolute_address,
                source_kind,
                notes,
                artifact_path,
                metadata_json,
                now,
                now,
                last_verified_at,
                last_game_build,
            ),
        )

        row = self.conn.execute(
            """
            SELECT candidate_id, metadata_json
            FROM candidates
            WHERE canonical_key = ?
            """,
            (canonical_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Candidate row was not found after upsert for key '{canonical_key}'.")

        candidate_id = int(row["candidate_id"])
        if evidence_kind and evidence_summary:
            self.conn.execute(
                """
                INSERT INTO candidate_evidence (
                    candidate_id,
                    session_id,
                    created_at,
                    event_kind,
                    summary,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    self._session_id,
                    now,
                    evidence_kind,
                    evidence_summary,
                    _to_json(evidence_metadata),
                ),
            )

        evidence_count = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM candidate_evidence WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()[0]
        )
        combined_metadata = _from_json(row["metadata_json"])
        combined_metadata = combined_metadata if isinstance(combined_metadata, dict) else metadata_payload
        final_confidence = _compute_candidate_confidence(
            confidence,
            evidence_count=evidence_count,
            metadata=combined_metadata if isinstance(combined_metadata, dict) else None,
            status=status,
        )
        self.conn.execute(
            """
            UPDATE candidates
            SET confidence = ?,
                last_seen_at = ?,
                last_verified_at = COALESCE(?, last_verified_at)
            WHERE candidate_id = ?
            """,
            (final_confidence, now, last_verified_at, candidate_id),
        )

        self.conn.commit()
        return candidate_id

    def update_candidate_status(
        self,
        candidate_id: int,
        status: str,
        *,
        note: str | None = None,
        verified: bool = False,
    ) -> None:
        row = self.conn.execute(
            "SELECT notes, confidence FROM candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Candidate {candidate_id} was not found.")

        existing_notes = row["notes"] or ""
        combined_notes = existing_notes
        if note:
            combined_notes = note if not existing_notes else f"{existing_notes}\n{note}"

        confidence = float(row["confidence"] or 0.0)
        if status == "stale":
            confidence = min(confidence, 0.35)
        elif status == "broken":
            confidence = min(confidence, 0.20)
        elif status == "promoted":
            confidence = max(confidence, 0.90)

        self.conn.execute(
            """
            UPDATE candidates
            SET status = ?,
                notes = ?,
                confidence = ?,
                last_seen_at = ?,
                last_verified_at = CASE WHEN ? THEN ? ELSE last_verified_at END
            WHERE candidate_id = ?
            """,
            (
                status,
                combined_notes,
                _clamp_confidence(confidence),
                utc_now_iso(),
                1 if verified else 0,
                utc_now_iso(),
                candidate_id,
            ),
        )
        self.conn.commit()

    def list_candidates(self, *, limit: int = 5000) -> list[CandidateRecord]:
        rows = self.conn.execute(
            """
            SELECT
                c.candidate_id,
                c.canonical_key,
                c.kind,
                c.label,
                c.status,
                c.confidence,
                c.value_type,
                c.module_name,
                c.module_rva,
                c.absolute_address,
                c.source_kind,
                c.notes,
                c.artifact_path,
                c.metadata_json,
                c.first_seen_at,
                c.last_seen_at,
                c.last_verified_at,
                c.last_game_build,
                (
                    SELECT COUNT(*)
                    FROM candidate_evidence e
                    WHERE e.candidate_id = c.candidate_id
                ) AS evidence_count
            FROM candidates c
            ORDER BY
                c.confidence DESC,
                COALESCE(c.last_verified_at, c.last_seen_at) DESC,
                c.candidate_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_candidate(row) for row in rows]

    def get_candidate(self, candidate_id: int) -> CandidateRecord | None:
        row = self.conn.execute(
            """
            SELECT
                c.candidate_id,
                c.canonical_key,
                c.kind,
                c.label,
                c.status,
                c.confidence,
                c.value_type,
                c.module_name,
                c.module_rva,
                c.absolute_address,
                c.source_kind,
                c.notes,
                c.artifact_path,
                c.metadata_json,
                c.first_seen_at,
                c.last_seen_at,
                c.last_verified_at,
                c.last_game_build,
                (
                    SELECT COUNT(*)
                    FROM candidate_evidence e
                    WHERE e.candidate_id = c.candidate_id
                ) AS evidence_count
            FROM candidates c
            WHERE c.candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_candidate(row)

    def list_candidate_evidence(self, candidate_id: int, *, limit: int = 100) -> list[CandidateEvidenceRecord]:
        rows = self.conn.execute(
            """
            SELECT evidence_id, candidate_id, session_id, created_at, event_kind, summary, metadata_json
            FROM candidate_evidence
            WHERE candidate_id = ?
            ORDER BY created_at DESC, evidence_id DESC
            LIMIT ?
            """,
            (candidate_id, limit),
        ).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def create_import(
        self,
        *,
        source_path: str,
        label: str,
        entry_count: int,
        warning_count: int = 0,
        notes: str | None = None,
        metadata: Any = None,
    ) -> int:
        imported_at = utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO imports (source_path, label, imported_at, entry_count, warning_count, notes, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_path) DO UPDATE SET
                label = excluded.label,
                imported_at = excluded.imported_at,
                entry_count = excluded.entry_count,
                warning_count = excluded.warning_count,
                notes = COALESCE(excluded.notes, imports.notes),
                metadata_json = COALESCE(excluded.metadata_json, imports.metadata_json)
            """,
            (
                source_path,
                label,
                imported_at,
                entry_count,
                warning_count,
                notes,
                _to_json(metadata),
            ),
        )
        row = self.conn.execute(
            "SELECT import_id FROM imports WHERE source_path = ?",
            (source_path,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Import row was not found after upsert for '{source_path}'.")
        self.conn.commit()
        return int(row["import_id"])

    def replace_import_entries(self, import_id: int, entries: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM import_entries WHERE import_id = ?", (import_id,))
        for entry in entries:
            self.conn.execute(
                """
                INSERT INTO import_entries (
                    import_id,
                    import_key,
                    label,
                    group_path,
                    kind,
                    status,
                    confidence,
                    value_type,
                    address_expression,
                    module_name,
                    module_rva,
                    resolved_address,
                    offsets_json,
                    notes,
                    metadata_json,
                    last_resolved_at,
                    last_error,
                    promoted_candidate_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    entry["import_key"],
                    entry["label"],
                    entry.get("group_path"),
                    entry.get("kind", "ct-entry"),
                    entry.get("status", "imported"),
                    _clamp_confidence(entry.get("confidence", 0.0)),
                    entry.get("value_type"),
                    entry.get("address_expression"),
                    entry.get("module_name"),
                    entry.get("module_rva"),
                    entry.get("resolved_address"),
                    _to_json(entry.get("offsets", [])),
                    entry.get("notes"),
                    _to_json(entry.get("metadata")),
                    entry.get("last_resolved_at"),
                    entry.get("last_error"),
                    entry.get("promoted_candidate_id"),
                ),
            )
        self.conn.execute(
            "UPDATE imports SET entry_count = ? WHERE import_id = ?",
            (len(entries), import_id),
        )
        self.conn.commit()

    def list_imports(self, *, limit: int = 100) -> list[ImportRecord]:
        rows = self.conn.execute(
            """
            SELECT import_id, source_path, label, imported_at, entry_count, warning_count, notes, metadata_json
            FROM imports
            ORDER BY imported_at DESC, import_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_import(row) for row in rows]

    def list_import_entries(self, *, import_id: int | None = None, limit: int = 5000) -> list[ImportEntryRecord]:
        query = """
            SELECT
                entry_id,
                import_id,
                import_key,
                label,
                group_path,
                kind,
                status,
                confidence,
                value_type,
                address_expression,
                module_name,
                module_rva,
                resolved_address,
                offsets_json,
                notes,
                metadata_json,
                last_resolved_at,
                last_error,
                promoted_candidate_id
            FROM import_entries
        """
        params: list[Any] = []
        if import_id is not None:
            query += " WHERE import_id = ?"
            params.append(import_id)
        query += """
            ORDER BY confidence DESC, COALESCE(last_resolved_at, '') DESC, label ASC, entry_id ASC
            LIMIT ?
        """
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_import_entry(row) for row in rows]

    def get_import_entry(self, entry_id: int) -> ImportEntryRecord | None:
        row = self.conn.execute(
            """
            SELECT
                entry_id,
                import_id,
                import_key,
                label,
                group_path,
                kind,
                status,
                confidence,
                value_type,
                address_expression,
                module_name,
                module_rva,
                resolved_address,
                offsets_json,
                notes,
                metadata_json,
                last_resolved_at,
                last_error,
                promoted_candidate_id
            FROM import_entries
            WHERE entry_id = ?
            """,
            (entry_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_import_entry(row)

    def update_import_entry_resolution(
        self,
        entry_id: int,
        *,
        status: str,
        confidence: float,
        resolved_address: int | None = None,
        module_name: str | None = None,
        module_rva: int | None = None,
        notes: str | None = None,
        metadata: Any = None,
        last_error: str | None = None,
        promoted_candidate_id: int | None = None,
    ) -> None:
        existing = self.get_import_entry(entry_id)
        if existing is None:
            raise KeyError(f"Import entry {entry_id} was not found.")

        metadata_payload = metadata if isinstance(metadata, dict) else existing.metadata
        if module_name and "module_name" not in metadata_payload:
            metadata_payload["module_name"] = module_name
        if module_rva is not None and "module_rva" not in metadata_payload:
            metadata_payload["module_rva"] = module_rva

        resolved_at = utc_now_iso() if status in {"resolved", "promoted", "stale", "broken"} else existing.last_resolved_at
        combined_notes = existing.notes or ""
        if notes:
            combined_notes = notes if not combined_notes else f"{combined_notes}\n{notes}"

        self.conn.execute(
            """
            UPDATE import_entries
            SET status = ?,
                confidence = ?,
                resolved_address = COALESCE(?, resolved_address),
                module_name = COALESCE(?, module_name),
                module_rva = COALESCE(?, module_rva),
                notes = ?,
                metadata_json = ?,
                last_resolved_at = ?,
                last_error = ?,
                promoted_candidate_id = COALESCE(?, promoted_candidate_id)
            WHERE entry_id = ?
            """,
            (
                status,
                _clamp_confidence(confidence),
                resolved_address,
                module_name,
                module_rva,
                combined_notes,
                _to_json(metadata_payload),
                resolved_at,
                last_error,
                promoted_candidate_id,
                entry_id,
            ),
        )
        self.conn.commit()

    def attach_import_entry_candidate(self, entry_id: int, candidate_id: int) -> None:
        self.conn.execute(
            """
            UPDATE import_entries
            SET promoted_candidate_id = ?,
                status = 'promoted',
                last_resolved_at = COALESCE(last_resolved_at, ?)
            WHERE entry_id = ?
            """,
            (candidate_id, utc_now_iso(), entry_id),
        )
        self.conn.commit()

    def build_session_snapshot(
        self,
        *,
        session_id: int | None = None,
        candidate_limit: int = 5000,
        event_limit: int = 5000,
        import_limit: int = 5000,
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        return {
            "session": {
                "session_id": session.session_id if session else None,
                "started_at": session.started_at if session else None,
                "ended_at": session.ended_at if session else None,
                "repo_root": session.repo_root if session else None,
                "scanner_version": session.scanner_version if session else None,
                "notes": session.notes if session else "",
                "db_path": str(self.db_path),
            },
            "summary": self.get_summary(),
            "events": [
                {
                    "event_id": event.event_id,
                    "session_id": event.session_id,
                    "created_at": event.created_at,
                    "kind": event.kind,
                    "summary": event.summary,
                    "metadata": event.metadata,
                }
                for event in self.list_events(limit=event_limit, session_id=session_id)
            ],
            "candidates": [
                {
                    "candidate_id": record.candidate_id,
                    "canonical_key": record.canonical_key,
                    "kind": record.kind,
                    "label": record.label,
                    "status": record.status,
                    "confidence": record.confidence,
                    "value_type": record.value_type,
                    "module_name": record.module_name,
                    "module_rva": record.module_rva,
                    "absolute_address": record.absolute_address,
                    "address_hex": record.address_hex,
                    "source_kind": record.source_kind,
                    "notes": record.notes,
                    "artifact_path": record.artifact_path,
                    "metadata": record.metadata,
                    "first_seen_at": record.first_seen_at,
                    "last_seen_at": record.last_seen_at,
                    "last_verified_at": record.last_verified_at,
                    "evidence_count": record.evidence_count,
                    "last_game_build": record.last_game_build,
                    "evidence": [
                        {
                            "evidence_id": evidence.evidence_id,
                            "created_at": evidence.created_at,
                            "event_kind": evidence.event_kind,
                            "summary": evidence.summary,
                            "metadata": evidence.metadata,
                        }
                        for evidence in self.list_candidate_evidence(record.candidate_id, limit=100)
                    ],
                }
                for record in self.list_candidates(limit=candidate_limit)
            ],
            "imports": [
                {
                    "import_id": import_record.import_id,
                    "source_path": import_record.source_path,
                    "label": import_record.label,
                    "imported_at": import_record.imported_at,
                    "entry_count": import_record.entry_count,
                    "warning_count": import_record.warning_count,
                    "notes": import_record.notes,
                    "metadata": import_record.metadata,
                    "entries": [
                        {
                            "entry_id": entry.entry_id,
                            "import_key": entry.import_key,
                            "label": entry.label,
                            "group_path": entry.group_path,
                            "kind": entry.kind,
                            "status": entry.status,
                            "confidence": entry.confidence,
                            "value_type": entry.value_type,
                            "address_expression": entry.address_expression,
                            "module_name": entry.module_name,
                            "module_rva": entry.module_rva,
                            "resolved_address": entry.resolved_address,
                            "resolved_address_hex": entry.resolved_address_hex,
                            "offsets": entry.offsets,
                            "notes": entry.notes,
                            "metadata": entry.metadata,
                            "last_resolved_at": entry.last_resolved_at,
                            "last_error": entry.last_error,
                            "promoted_candidate_id": entry.promoted_candidate_id,
                        }
                        for entry in self.list_import_entries(import_id=import_record.import_id, limit=import_limit)
                    ],
                }
                for import_record in self.list_imports(limit=200)
            ],
        }

    def get_summary(self) -> dict[str, int]:
        candidate_count = int(self.conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0])
        event_count = int(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        session_count = int(self.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
        import_count = int(self.conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0])
        import_entry_count = int(self.conn.execute("SELECT COUNT(*) FROM import_entries").fetchone()[0])
        return {
            "candidate_count": candidate_count,
            "event_count": event_count,
            "session_count": session_count,
            "import_count": import_count,
            "import_entry_count": import_entry_count,
        }
