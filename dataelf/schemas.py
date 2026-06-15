from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class TaskState(BaseModel):
    task_id: str
    user_query: str
    domain: str = "ai_index"
    intent: dict[str, Any] = Field(default_factory=dict)
    status: Literal["created", "running", "completed", "failed"] = "created"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    artifacts: list[str] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    report_id: str | None = None
    error: str | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission: Literal["read", "write", "analyze"]


class ToolCall(BaseModel):
    tool_call_id: str
    task_id: str
    tool_name: str
    input: dict[str, Any]
    started_at: datetime = Field(default_factory=now_utc)
    ended_at: datetime | None = None
    status: Literal["running", "success", "failed"] = "running"
    output_preview: str | None = None
    error: str | None = None


class ToolResult(BaseModel):
    tool_call_id: str
    output: dict[str, Any]


class RawArtifact(BaseModel):
    raw_id: str
    task_id: str
    connector: str
    endpoint: str
    request: dict[str, Any]
    content_hash: str
    content_uri: str
    created_at: datetime = Field(default_factory=now_utc)


class RecordEnvelope(BaseModel):
    record_id: str
    task_id: str
    source: str
    source_type: Literal["scholar", "paper", "institution", "news", "metric"]
    source_id: str
    observed_at: datetime = Field(default_factory=now_utc)
    payload: dict[str, Any]
    raw_id: str | None = None


class DomainObject(BaseModel):
    object_id: str
    task_id: str
    object_type: Literal["Scholar", "Paper", "Institution", "Field", "Venue"]
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)


class DomainRelation(BaseModel):
    relation_id: str
    task_id: str
    relation_type: Literal[
        "AUTHORED_BY",
        "AFFILIATED_WITH",
        "PUBLISHED_IN",
        "WORKS_ON",
        "HAS_PAPER",
        "HAS_SCHOLAR",
        "RELATED_TO_FIELD",
    ]
    source_object_id: str
    target_object_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_record_ids: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    evidence_id: str
    task_id: str
    title: str
    evidence_type: Literal["record", "object", "relation", "metric", "aggregate"]
    summary: str
    payload: dict[str, Any]
    source_ids: list[str] = Field(default_factory=list)
    created_by_tool_call_id: str | None = None
    confidence: float = 1.0


class Claim(BaseModel):
    claim_id: str
    task_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: Literal["unchecked", "supported", "unsupported"] = "unchecked"


class Report(BaseModel):
    report_id: str
    task_id: str
    title: str
    markdown: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
