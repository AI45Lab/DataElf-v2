from __future__ import annotations

import json
from pathlib import Path

from dataelf.discovery.base import DiscoveryContext
from dataelf.schemas import DiscoveryJob


def build_common_dynamic_discovery_prompt(
    job: DiscoveryJob,
    context: DiscoveryContext,
    *,
    title: str,
    backend_name: str,
    tool_appendix: str,
) -> str:
    workspace_path = Path(context.workspace_path).resolve()
    scope_json = json.dumps(job.scope, ensure_ascii=False, indent=2)
    constraints_json = json.dumps(job.constraints, ensure_ascii=False, indent=2)
    model = context.model or context.config.get("cubepi_model")
    model_line = f"\nPreferred model: `{model}`\n" if model else ""

    return f"""# {title}

You are DataElf `insights_explorer` for technology intelligence.

Goal: discover non-obvious, high-value insight candidates from AI Index data, workspace CSVs, Python analysis, and external web evidence. Do not produce a generic summary.
{model_line}
Backend: `{backend_name}`
Workspace: `{workspace_path}`

## Dynamic Loop

Use a dynamic agent loop:

inspect workspace -> decide next action -> fetch/analyze/write notes -> update hypotheses -> deepen promising signals -> synthesize when evidence is enough

Do not follow a rigid phase plan. Keep each step evidence-producing and compact.

## Workspace Contract

- `raw/ai_index/`: raw AI Index responses.
- `raw/web/`: external web observations.
- `tables/`: CSV tables for quantitative work. Prefer these over raw JSON.
- `scripts/`: Python scripts you write and run.
- `notes/`: plans, hypotheses, search summaries, uncertainty notes.
- `deep_dives/`: detailed reports for selected signals.
- `insights/`: required final outputs.

You must use DataElf AI Index SDK/tools; do not call AI Index HTTP directly. Use Python analysis when useful. Use external web search/fetch when available; if unavailable, state that limitation.

## Required Outputs

Always write:

- `insights/candidate_signals.json`
- `insights/insight_candidates.json`
- `insights/final_brief.md`

Also write supporting scripts, notes, deep dives, derived tables, and web/raw artifacts when useful.

## Quality Rules

- Do not output simple top-N rankings, generic summaries, or field restatements.
- Do not make every insight a trend/trajectory claim.
- Prefer mechanisms, anomalies, structural relationships, contradictions, ecosystem gaps, opportunities, or risks.
- Each final insight should connect at least two entity types, e.g. Paper + Institution, Scholar + Venue, Paper + Benchmark, or AI Index + WebSource.
- Include Python artifacts when possible.
- At least one insight should connect AI Index evidence with external web evidence when web is available.
- Include counterarguments, uncertainty, confidence, and next questions.
- Produce fewer stronger insights if evidence is thin.
- Do not fabricate facts.

## Minimal Schemas

`candidate_signals.json`:

```json
{{"candidate_signals":[{{"signal_id":"sig_001","signal_type":"...","summary":"...","why_might_matter":"...","supporting_tables":["papers.csv"],"related_entities":["Paper","Institution"],"suggested_deep_dive":["..."],"initial_score":{{"novelty":0.0,"magnitude":0.0,"strategic_relevance":0.0}},"status":"needs_deep_dive"}}]}}
```

`insight_candidates.json`:

```json
{{"insight_candidates":[{{"insight_id":"ins_001","title":"...","thesis":"...","why_now":"...","supporting_signals":["sig_001"],"analysis_artifacts":["scripts/analysis.py","deep_dives/sig_001.md"],"related_entities":["Topic:Agentic LLMs"],"external_support":[{{"source_id":"web_001","summary":"..."}}],"counterarguments":["..."],"confidence":0.0,"next_questions":["..."]}}]}}
```

## Backend Tool Appendix

{tool_appendix.strip()}

## User Task

`{job.seed_query or ""}`

Scope:

```json
{scope_json}
```

Constraints:

```json
{constraints_json}
```
"""
