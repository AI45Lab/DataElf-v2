# DataElf M1 Insight Discovery Runtime

DataElf M1 is a user-triggered Insight Discovery runtime for AI science intelligence.

```text
dataelf discover
  -> DiscoveryJob
  -> DiscoveryWorkflow
  -> AI Index domain pack
  -> job workspace
  -> insights_explore adapter
  -> raw AI Index responses + CSV tables
  -> candidate_signals.json / insight_candidates.json / final_brief.md
```

The current M1 keeps `insights_explore` as one replaceable adapter boundary, but does not add a factory or multi-framework switching. If the team changes frameworks later, replace the concrete adapter while preserving the `DiscoveryJob -> workspace artifacts` contract.

## Setup

```bash
uv venv
uv pip install -e ".[dev]"
```

Fixture mode is the default:

```bash
export DATAELF_AI_INDEX_MODE="fixture"
```

To use the live AI Index OpenAPI:

```bash
export DATAELF_AI_INDEX_MODE="api"
export AI_INDEX_BASE_URL="https://index.shlab.org.cn/api/v2"
export AI_INDEX_API_KEY="..."
```

## Run

```bash
dataelf init
dataelf discover "围绕 Agentic LLMs，基于 AI Index 和联网搜索，发现最近值得关注的 3 个 insight"
dataelf job workspace <job_id>
dataelf job insights <job_id>
dataelf job brief <job_id>
dataelf job review <job_id>
dataelf job logs <job_id>
```

## Discovery Workspace

Each job creates:

```text
.dataelf/workspaces/<job_id>/
  raw/ai_index/
  raw/web/
  domains/ai_index/tables/
  domains/ai_index/domain/
  scripts/
  notes/
  deep_dives/
  insights/
  reviews/
```

Key files:

```text
insights/candidate_signals.json
insights/insight_candidates.json
insights/final_brief.md
reviews/quality_review.json
workspace_index.json
```

AI Index scripts can import:

```python
from dataelf.domains.ai_index.client import AIIndexClient

client = AIIndexClient.from_env(workspace_path=".dataelf/workspaces/<job_id>")
papers = client.search_papers(sub_domains=["Agentic LLMs"], sort_type="heat", page=1, size=50)
papers_df = client.to_dataframe("papers", papers)
client.save_table("papers", papers_df)
```

## AI Index API

The AI Index connector supports:

- `POST /openapi/paper/search`
- `POST /openapi/institutions/search`
- `POST /openapi/scholar/search`
- `GET /openapi/institutions/:institution_id/funding-profile`

The default production base URL in code is `https://index.shlab.org.cn/api/v2`; override it with `AI_INDEX_BASE_URL`.

## Team Handoff

- Intern A can focus on `dataelf/discovery/insights_explorer.py`.
- Intern B can focus on `dataelf/domains/ai_index/domain.yaml`, `table_builder.py`, and future mapper/normalizer modules.
