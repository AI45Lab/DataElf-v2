from __future__ import annotations

import json
from pathlib import Path

from dataelf.schemas import QualityReviewResult, new_id


REQUIRED_INSIGHT_FIELDS = [
    "title",
    "thesis",
    "why_now",
    "confidence",
    "counterarguments",
    "next_questions",
]


def review_workspace(job_id: str, workspace_path: Path) -> QualityReviewResult:
    path = workspace_path / "insights" / "insight_candidates.json"
    warnings: list[str] = []
    payload: dict = {"insight_count": 0}
    if not path.exists():
        warnings.append("insight_candidates.json is missing.")
        return _result(job_id, "failed", warnings, payload)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"insight_candidates.json is not valid JSON: {exc}")
        return _result(job_id, "failed", warnings, payload)

    insights = data.get("insight_candidates", [])
    payload["insight_count"] = len(insights)
    if not 1 <= len(insights) <= 5:
        warnings.append("Expected 1-5 insight candidates.")
    for idx, item in enumerate(insights, start=1):
        missing = [field for field in REQUIRED_INSIGHT_FIELDS if field not in item or item.get(field) in (None, "", [])]
        if missing:
            warnings.append(f"Insight {idx} missing required fields: {', '.join(missing)}.")
        if not item.get("analysis_artifacts") and not item.get("supporting_signals"):
            warnings.append(f"Insight {idx} lacks analysis artifacts or supporting signals.")
        if not item.get("external_support"):
            warnings.append(f"Insight {idx} external support is weak or absent.")
        thesis = str(item.get("thesis", "")).lower()
        if "top" in thesis or "排名" in thesis:
            warnings.append(f"Insight {idx} may be mostly a top-N ranking; deepen the mechanism or anomaly.")
        confidence = item.get("confidence", 0)
        try:
            if not 0 <= float(confidence) <= 1:
                warnings.append(f"Insight {idx} confidence should be between 0 and 1.")
        except (TypeError, ValueError):
            warnings.append(f"Insight {idx} confidence should be numeric.")

    status = "pass" if not warnings else "pass_with_warnings"
    if not insights:
        status = "failed"
    return _result(job_id, status, warnings, payload)


def _result(job_id: str, status: str, warnings: list[str], payload: dict) -> QualityReviewResult:
    return QualityReviewResult(
        review_id=new_id("review"),
        job_id=job_id,
        review_status=status,
        warnings=warnings,
        recommended_revision=bool(warnings),
        payload=payload,
    )

