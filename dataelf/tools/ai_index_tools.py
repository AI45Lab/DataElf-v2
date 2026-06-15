from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dataelf.tools.runtime import ToolRuntime


def build_deepagents_tools(runtime: ToolRuntime, task_id: str) -> list[Callable[..., dict[str, Any]]]:
    def search_records(record_type: str, field: str = "AI Agent", time_window: str = "half_year") -> dict[str, Any]:
        """
        Search AI Index fixture records by type and field.

        Args:
            record_type: One of "institution", "paper", "scholar".
            field: Research field, e.g. "AI Agent".
            time_window: Usually "half_year".

        Returns:
            A dict with normalized record IDs and compact previews.
        """
        return runtime.run_tool(task_id, "search_records", {"record_type": record_type, "field": field, "time_window": time_window})

    def fetch_records(record_type: str, ids: list[str]) -> dict[str, Any]:
        """Fetch detailed fixture records by type and ids."""
        return runtime.run_tool(task_id, "fetch_records", {"record_type": record_type, "ids": ids})

    def model_records(record_ids: list[str]) -> dict[str, Any]:
        """
        Convert normalized records into DataElf DomainObjects and DomainRelations.
        Use this before trend analysis when the agent needs object/relation lineage.
        """
        return runtime.run_tool(task_id, "model_records", {"record_ids": record_ids})

    def analyze_trend(
        field: str = "AI Agent",
        target: str = "institution_hotness_growth",
        time_window: str = "half_year",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """
        Analyze institution hotness growth for a field.
        Computes current half-year hotness, previous half-year hotness, absolute growth, and growth rate.
        Returns ranked institutions and source record/object IDs.
        """
        return runtime.run_tool(task_id, "analyze_trend", {"field": field, "target": target, "time_window": time_window, "top_k": top_k})

    def write_evidence(
        title: str,
        evidence_type: str,
        summary: str,
        payload: dict[str, Any],
        source_ids: list[str],
    ) -> dict[str, Any]:
        """
        Write an evidence item into DataElf Evidence Store.
        Use this for any fact or metric that will be cited in the final report.
        Returns evidence_id.
        """
        return runtime.run_tool(task_id, "write_evidence", {"title": title, "evidence_type": evidence_type, "summary": summary, "payload": payload, "source_ids": source_ids})

    def draft_report(
        title: str,
        claims: list[dict[str, Any]],
        evidence_ids: list[str],
        markdown: str,
    ) -> dict[str, Any]:
        """
        Save a markdown report with explicit claims and evidence IDs.
        Each claim must contain text and evidence_ids.
        """
        return runtime.run_tool(task_id, "draft_report", {"title": title, "claims": claims, "evidence_ids": evidence_ids, "markdown": markdown})

    return [search_records, fetch_records, model_records, analyze_trend, write_evidence, draft_report]
