from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from dataelf.schemas import DiscoveryJob


class DiscoveryContext(BaseModel):
    workspace_path: str
    domain: str = "ai_index"
    domain_pack_path: str | None = None
    model: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    domain_pack: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    job_id: str
    status: str
    workspace_path: str
    candidate_signals_path: str | None = None
    insight_candidates_path: str | None = None
    final_brief_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class InsightsExplorer(Protocol):
    def run(self, job: DiscoveryJob, context: DiscoveryContext) -> DiscoveryResult:
        ...
