from __future__ import annotations

import json
from pathlib import Path

from dataelf.domains.ai_index.table_builder import ensure_table_schemas


WORKSPACE_DIRS = [
    "raw/ai_index",
    "raw/web",
    "tables",
    "scripts",
    "notes",
    "deep_dives",
    "insights",
    "prompts",
    "logs",
    "reviews",
    "domain",
    ".deepagents/agents",
]


def prepare_workspace(workspace_path: Path, domain: str = "ai_index") -> Path:
    workspace_path.mkdir(parents=True, exist_ok=True)
    for relative in WORKSPACE_DIRS:
        (workspace_path / relative).mkdir(parents=True, exist_ok=True)

    _write_json_if_missing(workspace_path / "insights" / "candidate_signals.json", {"candidate_signals": []})
    _write_json_if_missing(workspace_path / "insights" / "insight_candidates.json", {"insight_candidates": []})
    _write_text_if_missing(workspace_path / "insights" / "final_brief.md", "# Insight Discovery Brief\n")
    _write_json_if_missing(
        workspace_path / "reviews" / "quality_review.json",
        {"review_status": "pending", "warnings": [], "recommended_revision": False},
    )
    _write_text_if_missing(workspace_path / "notes" / "research_plan.md", "# Research Plan\n")
    _write_text_if_missing(workspace_path / "notes" / "hypotheses.md", "# Hypotheses\n")
    _write_text_if_missing(workspace_path / "notes" / "anomalies.md", "# Anomalies\n")
    _write_text_if_missing(workspace_path / "notes" / "search_summary.md", "# Search Summary\n")
    _write_text_if_missing(workspace_path / "domain" / "objects.jsonl", "")
    _write_text_if_missing(workspace_path / "domain" / "relations.jsonl", "")
    ensure_table_schemas(workspace_path)
    return workspace_path


def _write_json_if_missing(path: Path, payload: dict) -> None:
    if not path.exists():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")
