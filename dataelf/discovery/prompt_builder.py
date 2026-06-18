from __future__ import annotations

from pathlib import Path

from dataelf.discovery.base import DiscoveryContext
from dataelf.discovery.common_prompt_builder import build_common_dynamic_discovery_prompt
from dataelf.schemas import DiscoveryJob


def write_discovery_prompt(job: DiscoveryJob, context: DiscoveryContext) -> Path:
    workspace_path = Path(context.workspace_path)
    prompt_path = workspace_path / "prompts" / "discovery_prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(build_discovery_prompt(job, context), encoding="utf-8")
    return prompt_path


def build_discovery_prompt(job: DiscoveryJob, context: DiscoveryContext) -> str:
    return build_common_dynamic_discovery_prompt(
        job,
        context,
        title="DataElf DeepAgentsCode Insight Explorer",
        backend_name="deepagentscode",
        tool_appendix=_build_dcode_tool_appendix(),
    )


def _build_dcode_tool_appendix() -> str:
    return """### DeepAgentsCode Runtime

Run inside the job workspace. Use dcode native file/shell/web tools, but keep tool outputs compact.

Important dcode stability rules:

- Do not call `write_todos`; write plans to `notes/research_plan.md` instead.
- Use exactly one tool call per assistant turn. Do not fan out parallel `ls`, `read_file`, `glob`, `execute`, web, or task calls.
- Do not use `read_file` on CSV tables or raw JSON. Use Python to print compact `{table, columns, row_count}` summaries.
- Avoid large parallel tool batches. Prefer one compact script, then decide.
- Do not print raw API responses, full dataframes, or long CSV contents.

### AI Index

Use Python scripts under `scripts/`:

```python
from dataelf.domains.ai_index.client import AIIndexClient
client = AIIndexClient.from_env()
```

Available methods: `search_papers`, `search_institutions`, `search_scholars`, `fetch_institution_funding`, `save_raw`, `save_table`.

`search_*` and `fetch_institution_funding` automatically save raw responses under `raw/ai_index/` and update `tables/*.csv`.

### External Web

Use DeepAgentsCode `web_search` and `fetch_url` when useful. Save external observations to `tables/source_observations.csv`, `tables/external_findings.csv`, and `raw/web/`.

### Artifacts

Write valid JSON/Markdown directly to:

- `insights/candidate_signals.json`
- `insights/insight_candidates.json`
- `insights/final_brief.md`

### Subagents

`.deepagents/agents/` contains role shells. They are optional backend capabilities. Do not make `task` delegation the first required step; use it only if stable, otherwise continue in the main agent context."""
