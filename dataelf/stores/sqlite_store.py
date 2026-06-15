from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from dataelf.schemas import (
    DiscoveryJob,
    DomainObject,
    DomainRelation,
    QualityReviewResult,
    RawArtifact,
    RecordEnvelope,
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
            CREATE TABLE IF NOT EXISTS discovery_jobs (
              job_id TEXT PRIMARY KEY,
              trigger_type TEXT NOT NULL,
              job_type TEXT NOT NULL,
              seed_query TEXT,
              trigger_event_id TEXT,
              trigger_event_json TEXT,
              scope_json TEXT NOT NULL,
              constraints_json TEXT NOT NULL,
              status TEXT NOT NULL,
              workspace_path TEXT NOT NULL,
              insight_candidate_ids_json TEXT NOT NULL,
              state_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              error TEXT
            );

            CREATE TABLE IF NOT EXISTS quality_reviews (
              review_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              review_status TEXT NOT NULL,
              warnings_json TEXT NOT NULL,
              recommended_revision INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS raw_artifacts (
              raw_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              connector TEXT NOT NULL,
              endpoint TEXT NOT NULL,
              request_json TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              content_uri TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS records (
              record_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              source TEXT NOT NULL,
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              raw_id TEXT,
              observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS domain_objects (
              object_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              domain TEXT NOT NULL,
              object_type TEXT NOT NULL,
              name TEXT NOT NULL,
              properties_json TEXT NOT NULL,
              source_record_ids_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS domain_relations (
              relation_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              domain TEXT NOT NULL,
              relation_type TEXT NOT NULL,
              source_object_id TEXT NOT NULL,
              target_object_id TEXT NOT NULL,
              properties_json TEXT NOT NULL,
              source_record_ids_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trace_events (
              event_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
            )
            self.conn.commit()

    def save_discovery_job(self, job: DiscoveryJob) -> None:
        job.updated_at = now_utc()
        with self._lock:
            self.conn.execute(
                """
            INSERT INTO discovery_jobs(
              job_id,trigger_type,job_type,seed_query,trigger_event_id,trigger_event_json,
              scope_json,constraints_json,status,workspace_path,insight_candidate_ids_json,
              state_json,created_at,updated_at,error
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
              trigger_type=excluded.trigger_type,
              job_type=excluded.job_type,
              seed_query=excluded.seed_query,
              trigger_event_id=excluded.trigger_event_id,
              trigger_event_json=excluded.trigger_event_json,
              scope_json=excluded.scope_json,
              constraints_json=excluded.constraints_json,
              status=excluded.status,
              workspace_path=excluded.workspace_path,
              insight_candidate_ids_json=excluded.insight_candidate_ids_json,
              state_json=excluded.state_json,
              updated_at=excluded.updated_at,
              error=excluded.error
            """,
                (
                    job.job_id,
                    job.trigger_type,
                    job.job_type,
                    job.seed_query,
                    job.trigger_event_id,
                    _json(job.trigger_event) if job.trigger_event is not None else None,
                    _json(job.scope),
                    _json(job.constraints),
                    job.status,
                    job.workspace_path,
                    _json(job.insight_candidate_ids),
                    job.model_dump_json(),
                    _iso(job.created_at),
                    _iso(job.updated_at),
                    job.error,
                ),
            )
            self.conn.commit()

    def get_discovery_job(self, job_id: str) -> DiscoveryJob | None:
        with self._lock:
            row = self.conn.execute("SELECT state_json FROM discovery_jobs WHERE job_id=?", (job_id,)).fetchone()
        return DiscoveryJob.model_validate_json(row["state_json"]) if row else None

    def list_discovery_jobs(self) -> list[DiscoveryJob]:
        with self._lock:
            rows = self.conn.execute("SELECT state_json FROM discovery_jobs ORDER BY created_at DESC").fetchall()
        return [DiscoveryJob.model_validate_json(row["state_json"]) for row in rows]

    def save_quality_review(self, review: QualityReviewResult) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO quality_reviews(
              review_id,job_id,review_status,warnings_json,recommended_revision,payload_json,created_at
            )
            VALUES(?,?,?,?,?,?,?)
            """,
                (
                    review.review_id,
                    review.job_id,
                    review.review_status,
                    _json(review.warnings),
                    1 if review.recommended_revision else 0,
                    _json(review.payload),
                    _iso(review.created_at),
                ),
            )
            self.conn.commit()

    def get_latest_quality_review(self, job_id: str) -> QualityReviewResult | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM quality_reviews WHERE job_id=? ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return QualityReviewResult(
            review_id=row["review_id"],
            job_id=row["job_id"],
            review_status=row["review_status"],
            warnings=_loads(row["warnings_json"], []),
            recommended_revision=bool(row["recommended_revision"]),
            payload=_loads(row["payload_json"], {}),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def save_raw_artifact(self, artifact: RawArtifact) -> None:
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO raw_artifacts(
              raw_id,job_id,connector,endpoint,request_json,content_hash,content_uri,created_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
                (
                    artifact.raw_id,
                    artifact.job_id,
                    artifact.connector,
                    artifact.endpoint,
                    _json(artifact.request),
                    artifact.content_hash,
                    artifact.content_uri,
                    _iso(artifact.created_at),
                ),
            )
            self.conn.commit()

    def save_records(self, records: list[RecordEnvelope]) -> None:
        with self._lock:
            self.conn.executemany(
                """
            INSERT OR REPLACE INTO records(
              record_id,job_id,source,source_type,source_id,payload_json,raw_id,observed_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
                [
                    (
                        record.record_id,
                        record.job_id,
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

    def save_domain_objects(self, objects: list[DomainObject]) -> None:
        with self._lock:
            self.conn.executemany(
                """
            INSERT OR REPLACE INTO domain_objects(
              object_id,job_id,domain,object_type,name,properties_json,source_record_ids_json
            )
            VALUES(?,?,?,?,?,?,?)
            """,
                [
                    (
                        obj.object_id,
                        obj.job_id,
                        obj.domain,
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
              relation_id,job_id,domain,relation_type,source_object_id,target_object_id,
              properties_json,source_record_ids_json
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
                [
                    (
                        rel.relation_id,
                        rel.job_id,
                        rel.domain,
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

    def add_trace_event(self, job_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = new_id("evt")
        with self._lock:
            self.conn.execute(
                "INSERT INTO trace_events(event_id,job_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?)",
                (event_id, job_id, event_type, _json(payload), _iso(now_utc())),
            )
            self.conn.commit()
        return event_id

    def list_trace_events(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM trace_events WHERE job_id=? ORDER BY created_at", (job_id,)
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "job_id": row["job_id"],
                "event_type": row["event_type"],
                "payload": _loads(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
