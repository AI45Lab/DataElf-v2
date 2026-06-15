from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class DiscoveryJob(BaseModel):
    job_id: str
    trigger_type: Literal["user", "monitor"] = "user"
    job_type: str = "user_requested_discovery"
    seed_query: str | None = None
    trigger_event_id: str | None = None
    trigger_event: dict[str, Any] | None = None
    scope: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: Literal["created", "running", "completed", "failed"] = "created"
    workspace_path: str
    insight_candidate_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    error: str | None = None


class InsightCandidate(BaseModel):
    insight_id: str
    title: str
    thesis: str
    why_now: str
    supporting_signals: list[str] = Field(default_factory=list)
    analysis_artifacts: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    external_support: list[dict[str, Any]] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    next_questions: list[str] = Field(default_factory=list)


class QualityReviewResult(BaseModel):
    review_id: str
    job_id: str
    review_status: Literal["pass", "pass_with_warnings", "failed"] = "pass_with_warnings"
    warnings: list[str] = Field(default_factory=list)
    recommended_revision: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission: Literal["read", "write", "analyze"]


class RawArtifact(BaseModel):
    raw_id: str
    job_id: str
    connector: str
    endpoint: str
    request: dict[str, Any]
    content_hash: str
    content_uri: str
    created_at: datetime = Field(default_factory=now_utc)


class RecordEnvelope(BaseModel):
    record_id: str
    job_id: str
    source: str
    source_type: str
    source_id: str
    observed_at: datetime = Field(default_factory=now_utc)
    payload: dict[str, Any]
    raw_id: str | None = None


class DomainObject(BaseModel):
    object_id: str
    job_id: str
    domain: str
    object_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)


class DomainRelation(BaseModel):
    relation_id: str
    job_id: str
    domain: str
    relation_type: str
    source_object_id: str
    target_object_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)
