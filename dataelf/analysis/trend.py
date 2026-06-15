from __future__ import annotations

from typing import Any

from dataelf.schemas import DomainObject, RecordEnvelope


def analyze_institution_hotness_growth(
    records_or_objects: list[RecordEnvelope | DomainObject],
    field: str = "AI Agent",
    top_k: int = 5,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in records_or_objects:
        payload = item.payload if isinstance(item, RecordEnvelope) else item.properties
        if item.__class__.__name__ == "RecordEnvelope" and getattr(item, "source_type", None) != "institution":
            continue
        if item.__class__.__name__ == "DomainObject" and getattr(item, "object_type", None) != "Institution":
            continue
        if field and field not in payload.get("fields", []):
            continue
        hotness = payload.get("hotness", {})
        current = int(hotness.get("half_year", 0))
        previous = int(hotness.get("previous_half_year", 0))
        absolute_growth = current - previous
        growth_rate = absolute_growth / max(previous, 1)
        low_base = previous < 100
        rows.append(
            {
                "institution_id": payload.get("id") or payload.get("source_id"),
                "name": payload.get("name", "unknown"),
                "field": field,
                "current_hotness": current,
                "previous_hotness": previous,
                "absolute_growth": absolute_growth,
                "growth_rate": round(growth_rate, 4),
                "low_base": low_base,
                "supporting_record_ids": getattr(item, "source_record_ids", []) if isinstance(item, DomainObject) else [item.record_id],
                "supporting_object_ids": [item.object_id] if isinstance(item, DomainObject) else [],
            }
        )
    rows.sort(key=lambda row: (row["low_base"], -row["growth_rate"], -row["absolute_growth"], row["name"]))
    return {"ranking": rows[:top_k], "field": field, "top_k": top_k}
