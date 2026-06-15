from __future__ import annotations

from dataelf.schemas import ToolSpec


TOOL_SPECS = [
    ToolSpec(name="search_records", description="Search AI Index fixture records.", input_schema={}, output_schema={}, permission="read"),
    ToolSpec(name="fetch_records", description="Fetch AI Index fixture records by IDs.", input_schema={}, output_schema={}, permission="read"),
    ToolSpec(name="model_records", description="Convert records to domain objects and relations.", input_schema={}, output_schema={}, permission="write"),
    ToolSpec(name="analyze_trend", description="Analyze institution hotness growth.", input_schema={}, output_schema={}, permission="analyze"),
    ToolSpec(name="write_evidence", description="Write an evidence item.", input_schema={}, output_schema={}, permission="write"),
    ToolSpec(name="draft_report", description="Save claims and markdown report.", input_schema={}, output_schema={}, permission="write"),
]


def list_tool_specs() -> list[ToolSpec]:
    return TOOL_SPECS
