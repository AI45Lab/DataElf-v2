from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dataelf.discovery.base import DiscoveryResult


REQUIRED_INSIGHT_FIELDS = [
    "insight_id",
    "title",
    "thesis",
    "why_now",
    "analysis_artifacts",
    "counterarguments",
    "confidence",
]


def parse_discovery_result(workspace_path: Path, job_id: str = "") -> DiscoveryResult:
    warnings: list[str] = []
    error: str | None = None
    candidate_path = workspace_path / "insights" / "candidate_signals.json"
    insight_path = workspace_path / "insights" / "insight_candidates.json"
    brief_path = workspace_path / "insights" / "final_brief.md"

    candidate_signals_path = str(candidate_path) if candidate_path.exists() else None
    insight_candidates_path = str(insight_path) if insight_path.exists() else None
    final_brief_path = str(brief_path) if brief_path.exists() else None

    if not candidate_path.exists():
        warnings.append("candidate_signals.json is missing.")
    else:
        candidate_data = _read_json(candidate_path, warnings)
        if isinstance(candidate_data, dict) and not isinstance(candidate_data.get("candidate_signals"), list):
            warnings.append("candidate_signals.json should contain a candidate_signals list.")

    insights: list[dict[str, Any]] = []
    if not insight_path.exists():
        error = "insight_candidates.json is missing."
    else:
        insight_data = _read_json(insight_path, warnings)
        if insight_data is None:
            error = "insight_candidates.json is not valid JSON."
        elif not isinstance(insight_data, dict):
            error = "insight_candidates.json should contain a JSON object."
        elif not isinstance(insight_data.get("insight_candidates"), list):
            error = "insight_candidates.json should contain an insight_candidates list."
        else:
            insights = [item for item in insight_data["insight_candidates"] if isinstance(item, dict)]
            if not insights:
                warnings.append("insight_candidates.json contains no insight candidates.")
            for idx, item in enumerate(insights, start=1):
                missing = [field for field in REQUIRED_INSIGHT_FIELDS if item.get(field) in (None, "", [])]
                if missing:
                    warnings.append(f"Insight {idx} missing required fields: {', '.join(missing)}.")

    if not brief_path.exists():
        warnings.append("final_brief.md is missing.")

    if error:
        status = "failed"
    elif warnings:
        status = "incomplete"
    else:
        status = "completed"

    return DiscoveryResult(
        job_id=job_id,
        status=status,
        workspace_path=str(workspace_path),
        candidate_signals_path=candidate_signals_path,
        insight_candidates_path=insight_candidates_path,
        final_brief_path=final_brief_path,
        warnings=warnings,
        error=error,
    )


def load_insight_candidate_ids(workspace_path: Path) -> list[str]:
    path = workspace_path / "insights" / "insight_candidates.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    insights = data.get("insight_candidates", []) if isinstance(data, dict) else []
    return [str(item["insight_id"]) for item in insights if isinstance(item, dict) and item.get("insight_id")]


def _read_json(path: Path, warnings: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"{path.name} is not valid JSON: {exc}")
        return None
