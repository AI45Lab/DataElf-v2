# DataElf M1 CLI Demo

DataElf M1 is a minimal evidence-grounded data research runtime for AI science intelligence. The demo uses AI Index fixture data and keeps the system boundary explicit:

```text
DataElf CLI -> LangGraph workflow -> DeepAgentsAdapter -> DataElf tools -> SQLite/raw cache/evidence/report
```

Deep Agents can plan and choose tool calls, but it can only access data through DataElf tool wrappers.

## Setup

```bash
uv venv
uv pip install -e ".[dev]"
```

Configure a tool-calling model:

```bash
export DATAELF_MODEL="openai:gpt-5.4"
export OPENAI_API_KEY="..."
```

For an OpenAI-compatible endpoint:

```bash
export DATAELF_MODEL="openai:claude-sonnet-4-6-thinking"
export OPENAI_BASE_URL="https://api.boyuerichdata.opensphereai.com/v1"
export OPENAI_API_KEY="..."
```

## Run

```bash
dataelf init
dataelf seed fixtures/ai_index
dataelf run "分析最近半年 AI Agent 领域热度上升最快的机构，并给出证据"
dataelf task report <task_id>
dataelf task evidence <task_id>
dataelf task trace <task_id>
dataelf task logs <task_id>
```

Expected output includes a task id, a final markdown report, evidence IDs, and a tool trace similar to:

```text
search_records -> success
fetch_records -> success
model_records -> success
analyze_trend -> success
write_evidence -> success
draft_report -> success
```

## Notes

- Current data comes from local AI Index fixtures, not the real AI Index API.
- SQLite is the demo system of record.
- Raw connector responses are cached under `.dataelf/raw/`.
- The verifier currently checks evidence coverage and lineage presence; it does not judge real-world factual correctness.
- Production CLI does not fall back to a fake research loop. Tests monkeypatch `deepagents.create_deep_agent` only to validate the adapter contract.
