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
    return """### DeepAgentsCode CLI Runtime

You are running inside the DataElf job workspace through the DeepAgentsCode CLI runner.

Use DeepAgentsCode's native tools to inspect files, write files, execute Python/shell commands, and search/fetch the web.

### AI Index Access

When you need AI Index data, write Python scripts under `scripts/` and import:

```python
from dataelf.domains.ai_index.client import AIIndexClient

client = AIIndexClient.from_env()
```

Available SDK methods:

- `search_papers(...)`
- `search_institutions(...)`
- `search_scholars(...)`
- `fetch_institution_funding(...)`
- `save_raw(name, response, workspace_path=None)`
- `save_table(table_name, rows, workspace_path=None)`

`search_*` and `fetch_institution_funding` automatically save raw responses under `raw/ai_index/` and update normalized CSV tables under `tables/`.

Use `save_raw(...)` only for custom responses not already saved by `search_*`.
Use `save_table(...)` only for derived analysis tables you create.

### Python And Files

- Write Python scripts under `scripts/`.
- Run scripts from the workspace.
- Return compact summaries from scripts.
- Write large details to `notes/`, `tables/`, `deep_dives/`, or `raw/`.
- Do not print raw API responses, full dataframes, or long CSV contents.
- If a script or model step fails after a large batch, retry with smaller batches and summarize intermediate files instead of abandoning the task.

### External Web

Use DeepAgentsCode `web_search` and `fetch_url` when useful.

External search should explain, validate, or challenge AI Index signals. Look for benchmark leaderboards, GitHub repositories, project pages, arXiv or paper pages, institution announcements, technical blogs, funding/news events, datasets, and benchmark pages.

Write external observations to:

- `tables/source_observations.csv`
- `tables/external_findings.csv`
- `raw/web/`

If web search is unavailable, say so explicitly in the final brief.

### Artifact Writing

Write final artifacts directly to:

- `insights/candidate_signals.json`
- `insights/insight_candidates.json`
- `insights/final_brief.md`

Make sure the JSON files are valid JSON and match the common schemas.

### DeepAgentsCode Subagents

Project subagent shells are available under `.deepagents/agents/`:

- `breadth-scout`: broad AI Index and local table scan; generate candidate signal coverage.
- `code-analyst`: Python analysis, joins, aggregations, anomaly detection, and derived tables.
- `web-investigator`: external web_search / fetch_url investigation.
- `skeptic`: challenge evidence, low-base effects, obviousness, and alternative explanations.
- `insight-synthesizer`: produce final `insight_candidates.json` and `final_brief.md`.

These subagents are backend capabilities, not the common discovery method. Do not make `task` delegation a required first step. First inspect the workspace and proceed in the main agent context. Use the DeepAgentsCode `task` tool only if it is clearly available and stable in the current run. If `task` delegation fails or appears unstable, continue in the main agent context and write concise role-specific notes under `notes/` instead."""
