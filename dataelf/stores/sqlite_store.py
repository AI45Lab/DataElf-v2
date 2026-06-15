from __future__ import annotations

import json
import sqlite3
from threading import RLock
from datetime import datetime
from pathlib import Path
from typing import Any

from dataelf.schemas import (
    Claim,
    DomainObject,
    DomainRelation,
    Evidence,
    RawArtifact,
    RecordEnvelope,
    Report,
    TaskState,
    ToolCall,
    new_id,
    now_utc,
)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _loads(data: str | None, default: Any = None) -> Any:
    if data is None:
        return default
    return json.loads(data)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class SQLiteStore:
    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = RLock()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def init_schema(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY,
              state_json TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_calls (
              tool_call_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              tool_name TEXT NOT NULL,
              input_json TEXT NOT NULL,
              output_json TEXT,
              status TEXT NOT NULL,
              error TEXT,
              started_at TEXT NOT NULL,
              ended_at TEXT
            );

            CREATE TABLE IF NOT EXISTS raw_artifacts (
              raw_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              connector TEXT NOT NULL,
              endpoint TEXT NOT NULL,
              request_json TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              content_uri TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS records (
              record_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              source TEXT NOT NULL,
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              raw_id TEXT,
              observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS domain_objects (
              object_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              object_type TEXT NOT NULL,
              name TEXT NOT NULL,
              properties_json TEXT NOT NULL,
              source_record_ids_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS domain_relations (
              relation_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              relation_type TEXT NOT NULL,
              source_object_id TEXT NOT NULL,
              target_object_id TEXT NOT NULL,
              properties_json TEXT NOT NULL,
              source_record_ids_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence (
              evidence_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              title TEXT NOT NULL,
              evidence_type TEXT NOT NULL,
              summary TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              source_ids_json TEXT NOT NULL,
              created_by_tool_call_id TEXT,
              confidence REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS claims (
              claim_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              text TEXT NOT NULL,
              evidence_ids_json TEXT NOT NULL,
              verification_status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
              report_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              title TEXT NOT NULL,
              markdown TEXT NOT NULL,
              claim_ids_json TEXT NOT NULL,
              evidence_ids_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trace_events (
              event_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
            )
            self.conn.commit()

    def save_task_state(self, state: TaskState) -> None:
        state.updated_at = now_utc()
        with self._lock:
            self.conn.execute(
                """
            INSERT INTO tasks(task_id,state_json,status,created_at,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
              state_json=excluded.state_json,
              status=excluded.status,
              updated_at=excluded.updated_at
            """,
            (
                state.task_id,
                state.model_dump_json(),
                state.status,
                _iso(state.created_at),
                _iso(state.updated_at),
            ),
            )
            self.conn.commit()

    def get_task_state(self, task_id: str) -> TaskState | None:
        with self._lock:
            row = self.conn.execute("SELECT state_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return TaskState.model_validate_json(row["state_json"]) if row else None

    def list_task_states(self) -> list[TaskState]:
        with self._lock:
            rows = self.conn.execute("SELECT state_json FROM tasks ORDER BY created_at DESC").fetchall()
        return [TaskState.model_validate_json(row["state_json"]) for row in rows]

    def save_tool_call(self, call: ToolCall, output: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT INTO tool_calls(
              tool_call_id,task_id,tool_name,input_json,output_json,status,error,started_at,ended_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tool_call_id) DO UPDATE SET
              output_json=excluded.output_json,
              status=excluded.status,
              error=excluded.error,
              ended_at=excluded.ended_at
            """,
            (
                call.tool_call_id,
                call.task_id,
                call.tool_name,
                _json(call.input),
                _json(output) if output is not None else None,
                call.status,
                call.error,
                _iso(call.started_at),
                _iso(call.ended_at),
            ),
            )
            self.conn.commit()

    def list_tool_calls(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM tool_calls WHERE task_id=? ORDER BY started_at", (task_id,)
            ).fetchall()
        return [
            {
                "tool_call_id": row["tool_call_id"],
                "task_id": row["task_id"],
                "tool_name": row["tool_name"],
                "input": _loads(row["input_json"], {}),
                "output": _loads(row["output_json"], {}),
                "status": row["status"],
                "error": row["error"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
            }
            for row in rows
        ]

    def save_raw_artifact(self, artifact: RawArtifact) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO raw_artifacts(
              raw_id,task_id,connector,endpoint,request_json,content_hash,content_uri,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                artifact.raw_id,
                artifact.task_id,
                artifact.connector,
                artifact.endpoint,
                _json(artifact.request),
                artifact.content_hash,
                artifact.content_uri,
                _iso(artifact.created_at),
            ),
            )
            self.conn.commit()

    def list_raw_artifacts(self, task_id: str) -> list[RawArtifact]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM raw_artifacts WHERE task_id=? ORDER BY created_at", (task_id,)
            ).fetchall()
        return [
            RawArtifact(
                raw_id=row["raw_id"],
                task_id=row["task_id"],
                connector=row["connector"],
                endpoint=row["endpoint"],
                request=_loads(row["request_json"], {}),
                content_hash=row["content_hash"],
                content_uri=row["content_uri"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def save_records(self, records: list[RecordEnvelope]) -> None:
        with self._lock:
            self.conn.executemany(
                """
            INSERT OR REPLACE INTO records(
              record_id,task_id,source,source_type,source_id,payload_json,raw_id,observed_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            [
                (
                    record.record_id,
                    record.task_id,
                    record.source,
                    record.source_type,
                    record.source_id,
                    _json(record.payload),
                    record.raw_id,
                    _iso(record.observed_at),
                )
                for record in records
            ],
            )
            self.conn.commit()

    def get_records(self, record_ids: list[str]) -> list[RecordEnvelope]:
        if not record_ids:
            return []
        placeholders = ",".join("?" for _ in record_ids)
        with self._lock:
            rows = self.conn.execute(
                f"SELECT * FROM records WHERE record_id IN ({placeholders})", record_ids
            ).fetchall()
        by_id = {row["record_id"]: self._record_from_row(row) for row in rows}
        return [by_id[record_id] for record_id in record_ids if record_id in by_id]

    def list_records(self, task_id: str, source_type: str | None = None) -> list[RecordEnvelope]:
        if source_type:
            with self._lock:
                rows = self.conn.execute(
                    "SELECT * FROM records WHERE task_id=? AND source_type=? ORDER BY observed_at",
                    (task_id, source_type),
                ).fetchall()
        else:
            with self._lock:
                rows = self.conn.execute(
                    "SELECT * FROM records WHERE task_id=? ORDER BY observed_at", (task_id,)
                ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def _record_from_row(self, row: sqlite3.Row) -> RecordEnvelope:
        return RecordEnvelope(
            record_id=row["record_id"],
            task_id=row["task_id"],
            source=row["source"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            payload=_loads(row["payload_json"], {}),
            raw_id=row["raw_id"],
        )

    def save_domain_objects(self, objects: list[DomainObject]) -> None:
        with self._lock:
            self.conn.executemany(
                """
            INSERT OR REPLACE INTO domain_objects(
              object_id,task_id,object_type,name,properties_json,source_record_ids_json
            )
            VALUES(?,?,?,?,?,?)
            """,
            [
                (
                    obj.object_id,
                    obj.task_id,
                    obj.object_type,
                    obj.name,
                    _json(obj.properties),
                    _json(obj.source_record_ids),
                )
                for obj in objects
            ],
            )
            self.conn.commit()

    def save_domain_relations(self, relations: list[DomainRelation]) -> None:
        with self._lock:
            self.conn.executemany(
                """
            INSERT OR REPLACE INTO domain_relations(
              relation_id,task_id,relation_type,source_object_id,target_object_id,
              properties_json,source_record_ids_json
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            [
                (
                    rel.relation_id,
                    rel.task_id,
                    rel.relation_type,
                    rel.source_object_id,
                    rel.target_object_id,
                    _json(rel.properties),
                    _json(rel.source_record_ids),
                )
                for rel in relations
            ],
            )
            self.conn.commit()

    def list_domain_objects(self, task_id: str, object_type: str | None = None) -> list[DomainObject]:
        if object_type:
            with self._lock:
                rows = self.conn.execute(
                    "SELECT * FROM domain_objects WHERE task_id=? AND object_type=? ORDER BY name",
                    (task_id, object_type),
                ).fetchall()
        else:
            with self._lock:
                rows = self.conn.execute(
                    "SELECT * FROM domain_objects WHERE task_id=? ORDER BY object_type,name", (task_id,)
                ).fetchall()
        return [
            DomainObject(
                object_id=row["object_id"],
                task_id=row["task_id"],
                object_type=row["object_type"],
                name=row["name"],
                properties=_loads(row["properties_json"], {}),
                source_record_ids=_loads(row["source_record_ids_json"], []),
            )
            for row in rows
        ]

    def list_domain_relations(self, task_id: str) -> list[DomainRelation]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM domain_relations WHERE task_id=? ORDER BY relation_type", (task_id,)
            ).fetchall()
        return [
            DomainRelation(
                relation_id=row["relation_id"],
                task_id=row["task_id"],
                relation_type=row["relation_type"],
                source_object_id=row["source_object_id"],
                target_object_id=row["target_object_id"],
                properties=_loads(row["properties_json"], {}),
                source_record_ids=_loads(row["source_record_ids_json"], []),
            )
            for row in rows
        ]

    def save_evidence(self, evidence: Evidence) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO evidence(
              evidence_id,task_id,title,evidence_type,summary,payload_json,source_ids_json,
              created_by_tool_call_id,confidence
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                evidence.evidence_id,
                evidence.task_id,
                evidence.title,
                evidence.evidence_type,
                evidence.summary,
                _json(evidence.payload),
                _json(evidence.source_ids),
                evidence.created_by_tool_call_id,
                evidence.confidence,
            ),
            )
            self.conn.commit()

    def list_evidence(self, task_id: str) -> list[Evidence]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM evidence WHERE task_id=? ORDER BY evidence_id", (task_id,)
            ).fetchall()
        return [
            Evidence(
                evidence_id=row["evidence_id"],
                task_id=row["task_id"],
                title=row["title"],
                evidence_type=row["evidence_type"],
                summary=row["summary"],
                payload=_loads(row["payload_json"], {}),
                source_ids=_loads(row["source_ids_json"], []),
                created_by_tool_call_id=row["created_by_tool_call_id"],
                confidence=row["confidence"],
            )
            for row in rows
        ]

    def save_claim(self, claim: Claim) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO claims(
              claim_id,task_id,text,evidence_ids_json,verification_status
            )
            VALUES(?,?,?,?,?)
            """,
            (
                claim.claim_id,
                claim.task_id,
                claim.text,
                _json(claim.evidence_ids),
                claim.verification_status,
            ),
            )
            self.conn.commit()

    def list_claims(self, task_id: str) -> list[Claim]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM claims WHERE task_id=? ORDER BY claim_id", (task_id,)
            ).fetchall()
        return [
            Claim(
                claim_id=row["claim_id"],
                task_id=row["task_id"],
                text=row["text"],
                evidence_ids=_loads(row["evidence_ids_json"], []),
                verification_status=row["verification_status"],
            )
            for row in rows
        ]

    def save_report(self, report: Report) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO reports(
              report_id,task_id,title,markdown,claim_ids_json,evidence_ids_json,created_at
            )
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                report.report_id,
                report.task_id,
                report.title,
                report.markdown,
                _json(report.claim_ids),
                _json(report.evidence_ids),
                _iso(report.created_at),
            ),
            )
            self.conn.commit()

    def get_latest_report(self, task_id: str) -> Report | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM reports WHERE task_id=? ORDER BY created_at DESC LIMIT 1", (task_id,)
            ).fetchone()
        if not row:
            return None
        return Report(
            report_id=row["report_id"],
            task_id=row["task_id"],
            title=row["title"],
            markdown=row["markdown"],
            claim_ids=_loads(row["claim_ids_json"], []),
            evidence_ids=_loads(row["evidence_ids_json"], []),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def add_trace_event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = new_id("evt")
        with self._lock:
            self.conn.execute(
                "INSERT INTO trace_events(event_id,task_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?)",
                (event_id, task_id, event_type, _json(payload), _iso(now_utc())),
            )
            self.conn.commit()
        return event_id

    def list_trace_events(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM trace_events WHERE task_id=? ORDER BY created_at", (task_id,)
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "task_id": row["task_id"],
                "event_type": row["event_type"],
                "payload": _loads(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
