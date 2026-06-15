from __future__ import annotations

import json
from pathlib import Path

from dataelf.analysis.trend import analyze_institution_hotness_growth
from dataelf.schemas import RecordEnvelope


def test_trend_analysis_ranks_openagent_lab_first() -> None:
    institutions = json.loads(Path("fixtures/ai_index/institutions.json").read_text(encoding="utf-8"))
    records = [
        RecordEnvelope(
            record_id=f"rec_{item['id']}",
            task_id="task_test",
            source="fixture",
            source_type="institution",
            source_id=item["id"],
            payload=item,
        )
        for item in institutions
    ]
    result = analyze_institution_hotness_growth(records, field="AI Agent", top_k=5)
    top = result["ranking"][0]
    assert top["institution_id"] == "inst_openagent_lab"
    assert top["absolute_growth"] == 10000
    assert top["growth_rate"] == round(10000 / 5200, 4)
    assert all(not row["low_base"] for row in result["ranking"][:3])
