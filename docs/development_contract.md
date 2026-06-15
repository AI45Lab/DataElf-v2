# DataElf M1 Development Contract

This document is for interns and AI coding agents working on DataElf. Read it before changing architecture, tools, adapters, storage, schemas, or AutoResearch.

DataElf is not a chatbot plus tools. It is an evidence-grounded data research runtime. The most important rule is:

> AutoResearch may decide what to do next, but DataElf Harness owns state, tool invocation, raw cache, normalized records, TaskGraph objects/relations, evidence, claims, reports, and verification.

## Current Architecture

The current M1 flow is:

```text
CLI
  -> LangGraph top-level workflow
    -> prepare runtime
    -> initialize task
    -> parse intent
    -> DeepAgentsAdapter.run(task_state)
      -> deepagents.create_deep_agent(...)
      -> DataElf tool wrappers only
        -> ToolRuntime.run_tool(...)
          -> connector / raw cache / normalize / model / analyze / evidence / report
    -> evidence verifier
    -> SQLite task state
```

Key files:

- `dataelf/cli.py`: CLI commands such as `init`, `seed`, `run`, `task report`, `task evidence`, `task trace`, `task logs`.
- `dataelf/workflow.py`: DataElf Harness implemented as a LangGraph workflow.
- `dataelf/schemas.py`: semantic contracts shared by all modules.
- `dataelf/adapters/deepagents_adapter.py`: Deep Agents integration boundary.
- `dataelf/tools/ai_index_tools.py`: Python functions exposed to Deep Agents.
- `dataelf/tools/runtime.py`: actual DataElf tool execution, trace, raw cache, normalized record, evidence, claim, and report writes.
- `dataelf/connectors/ai_index_fixture.py`: fixture connector simulating AI Index APIs.
- `dataelf/stores/sqlite_store.py`: SQLite system of record.
- `dataelf/stores/raw_cache.py`: raw response JSON cache.
- `dataelf/modeling/ai_index_modeler.py`: normalized records to DomainObject / DomainRelation.
- `dataelf/analysis/trend.py`: trend analysis.
- `dataelf/verifier/evidence_verifier.py`: claim/evidence/report coverage verifier.
- `fixtures/ai_index/*`: current mock AI Index data.

## Semantic Contracts

DataElf modules must communicate using the Pydantic objects in `dataelf/schemas.py`.

Current core objects:

- `TaskState`: lifecycle state for one task.
- `ToolSpec`, `ToolCall`, `ToolResult`: tool metadata and execution trace.
- `RawArtifact`: raw connector response metadata.
- `RecordEnvelope`: normalized record from any connector.
- `DomainObject`: task-level entity such as Scholar, Paper, Institution, Field, Venue.
- `DomainRelation`: task-level relation such as AUTHORED_BY, AFFILIATED_WITH, HAS_PAPER, WORKS_ON.
- `Evidence`: report-citable evidence item with lineage.
- `Claim`: verifiable conclusion bound to evidence IDs.
- `Report`: final markdown report bound to claims and evidence.

Do not invent parallel object formats inside a new module. If a field is missing, extend `schemas.py` deliberately and update storage/tests.

## Data Ownership Rules

### DataElf Harness Owns

Only DataElf Harness / ToolRuntime / Store may perform these actions:

- Invoke domain tools.
- Write tool call trace.
- Call connectors.
- Write raw API/fixture responses to raw cache.
- Write `RawArtifact`.
- Write `RecordEnvelope`.
- Write `DomainObject` / `DomainRelation`.
- Write `Evidence`.
- Write `Claim`.
- Write `Report`.
- Update `TaskState`.
- Run verification.

### AutoResearch Owns

AutoResearch owns planning and research intelligence only:

- choose next action;
- decide which DataElf tool to call;
- compare candidate findings;
- draft candidate claims;
- propose evidence candidates;
- draft report text;
- use scratchpad/todo/subagents if allowed by Harness.

AutoResearch does not own DataElf source of truth.

## AutoResearch Boundary

AutoResearch may be implemented by Deep Agents, AutoGen, a custom ReAct loop, a LangGraph subgraph, or another framework. The implementation can change, but the boundary cannot.

Future AutoResearch should communicate to Harness using standard candidate/action objects such as:

- `ActionProposal`: requested next controlled action.
- `InsightDraft`: tentative insight from explored data.
- `ClaimCandidate`: candidate conclusion text and supporting evidence references.
- `EvidenceCandidate`: candidate evidence payload and lineage references.
- `ReportDraft`: draft markdown plus claim/evidence bindings.

Even if these classes are not all implemented yet, new AutoResearch code should be designed around this direction.

AutoResearch must not:

- directly open SQLite connections;
- directly write `.dataelf/raw`;
- directly write records, objects, relations, evidence, claims, or reports;
- directly call AI Index APIs or external APIs outside DataElf connectors;
- silently swallow tool errors;
- treat scratchpad notes as verified evidence;
- create final claims without evidence IDs.

## Tool Invocation Rules

All tool execution must go through:

```text
DataElf tool wrapper -> ToolRuntime.run_tool(...) -> concrete handler
```

Current wrapper factory:

```text
dataelf/tools/ai_index_tools.py
```

Current runtime:

```text
dataelf/tools/runtime.py
```

`ToolRuntime.run_tool` is responsible for:

1. creating `ToolCall`;
2. writing running status;
3. logging `tool_start`;
4. dispatching to the concrete tool;
5. writing success/failure result;
6. logging `tool_success` or `tool_failed`;
7. re-raising failures.

Do not call connector/modeler/analyzer/store directly from an agent adapter.

## Connector Rules

Connectors simulate or access external data sources. A connector returns API-shaped responses:

```json
{
  "source": "ai_index_fixture",
  "endpoint": "search_institutions",
  "request": {"field": "AI Agent", "time_window": "half_year"},
  "data": []
}
```

Connectors should not write SQLite or raw files themselves. The tool runtime persists connector responses as:

```text
connector response -> RawCache JSON file -> RawArtifact row -> RecordEnvelope rows
```

Current connector:

```text
dataelf/connectors/ai_index_fixture.py
```

When adding a real AI Index connector, keep the same response shape. Do not make downstream tools depend on provider-specific raw fields unless they are normalized into `RecordEnvelope`.

## Raw Cache and SQLite Store

Raw responses are stored as JSON files under:

```text
.dataelf/raw/<sha256>.json
```

Metadata and all semantic state are stored in SQLite:

```text
.dataelf/dataelf.sqlite
```

Current SQLite tables include:

- `tasks`
- `tool_calls`
- `raw_artifacts`
- `records`
- `domain_objects`
- `domain_relations`
- `evidence`
- `claims`
- `reports`
- `trace_events`

All SQLite access should go through `SQLiteStore`. Do not scatter SQL across tools, adapters, or connectors.

## Normalized Records to Entities and Relations

The modeling path is:

```text
RecordEnvelope[] -> DomainObject[] + DomainRelation[]
```

Current mapper:

```text
dataelf/modeling/ai_index_modeler.py
```

Current minimal rules:

- institution record -> `Institution`
- paper record -> `Paper`
- scholar record -> `Scholar`
- fields -> `Field`
- paper venue -> `Venue`
- paper author -> `Paper AUTHORED_BY Scholar`
- paper institution -> `Institution HAS_PAPER Paper`
- scholar institution -> `Scholar AFFILIATED_WITH Institution`
- scholar/institution works on field -> `WORKS_ON`
- paper related to field -> `RELATED_TO_FIELD`

Entity IDs should remain stable and task-scoped. Do not introduce another ID scheme without updating tests and lineage rules.

## Evidence and Claims

Evidence must be written through `write_evidence`.

Rules:

- every evidence item must include at least one `source_id`;
- `source_id` should reference records, objects, or relations already in DataElf store;
- every claim in a final report must reference at least one evidence ID;
- final report must be written through `draft_report`;
- verifier must run after AutoResearch.

Evidence is not just a quote or a paragraph. It is a lineage-bearing object.

## Deep Agents Usage

Current implementation uses Deep Agents as an AutoResearch engine:

```text
dataelf/adapters/deepagents_adapter.py
```

The adapter:

- builds DataElf tool wrappers;
- initializes Deep Agents;
- invokes the agent;
- reads evidence/claims/report back from SQLite;
- updates `TaskState`.

For OpenAI-compatible providers, the adapter initializes LangChain chat models with `use_responses_api=False`, because the current compatible endpoint supports `/chat/completions` rather than `/responses`.

### Built-in Deep Agents Tools

Deep Agents can provide internal tools such as todo, virtual filesystem, grep, file write, subagents, and execute. Opening these tools is allowed only if Harness explicitly configures safe boundaries.

Allowed direction:

- virtual scratchpad under controlled paths such as `/scratch/**`;
- todo/planning;
- subagents for reasoning;
- context summarization.

Forbidden direction:

- shell `execute`;
- direct real filesystem read/write;
- direct connector/API calls;
- writing final evidence/report outside DataElf tools;
- using scratchpad as source of truth.

The safe principle is:

> Deep Agents may have a scratchpad, but DataElf Store is the source of truth.

If we expose scratchpad long term, prefer DataElf wrapper tools such as:

- `write_research_note`
- `read_research_note`
- `list_research_notes`

That lets DataElf trace the scratchpad too.

## Workflow Rules

The outer workflow is stable and owned by DataElf:

```text
prepare -> init_task -> intent_parse -> auto_research -> evidence_verify
```

Do not let AutoResearch dynamically skip verifier, directly finalize reports, or replace top-level orchestration.

If you add workflow nodes, they should be coarse-grained DataElf lifecycle nodes, not agent micro-steps. Agent micro-steps belong inside AutoResearch.

## CLI Rules

CLI should be thin:

- parse user command;
- create config/store;
- call workflow or store query;
- render with Rich.

Do not put business logic in `cli.py`.

## Adding a New Tool

To add a DataElf tool:

1. Add or update schema if needed in `dataelf/schemas.py`.
2. Add a tool spec in `dataelf/tools/registry.py`.
3. Add a wrapper function in `dataelf/tools/ai_index_tools.py` or a domain-specific tool module.
4. Add a handler in `ToolRuntime._dispatch`.
5. Ensure the handler writes through `SQLiteStore` and logs through `ToolRuntime`.
6. Add tests for success, failure, and lineage.

Do not expose a tool to AutoResearch if its side effects are not traceable.

## Adding a New Connector

To add a connector:

1. Implement API-shaped methods returning `{source, endpoint, request, data}`.
2. Keep connector methods side-effect free.
3. Normalize outputs into `RecordEnvelope` in ToolRuntime or a normalizer.
4. Write raw responses through `RawCache`.
5. Write raw metadata through `SQLiteStore.save_raw_artifact`.
6. Add tests with fixture data.

## Adding a New Domain

New domains should reuse the same runtime concepts:

- connector;
- raw cache;
- normalized record;
- domain object;
- domain relation;
- evidence;
- claim;
- report;
- trace;
- verifier.

Do not create a domain-specific parallel runtime unless there is a strong reason and a migration plan.

## Things Not to Randomly Change

Do not casually change:

- object names in `schemas.py`;
- ID formats for task, record, object, relation, evidence, claim, report;
- SQLite table names or JSON column meanings;
- the fact that evidence requires lineage;
- the fact that reports must bind claims and evidence;
- the top-level workflow ownership;
- the ToolRuntime tracing path;
- connector response shape;
- raw cache hash behavior.

If you need to change any of these, update tests and write a migration note.

## Required Tests for Meaningful Changes

At minimum, keep these passing:

```bash
python -m pytest -q
```

Current tests cover:

- trend ranking;
- evidence lineage and verifier;
- DeepAgentsAdapter contract without real LLM;
- CLI init/seed smoke.

Add new tests when touching:

- storage schema;
- tool runtime;
- AutoResearch adapter;
- connector normalization;
- evidence/claim/report verification.

## Mental Model

Think of DataElf as three layers:

```text
Research intelligence:
  Deep Agents / AutoGen / ReAct / subagents / scratchpad

DataElf semantic runtime:
  TaskState / ToolRuntime / Connector / RawArtifact / RecordEnvelope /
  DomainObject / DomainRelation / Evidence / Claim / Report / Verifier

Storage and audit:
  SQLite / raw JSON files / trace events / CLI inspection
```

The research intelligence layer can evolve quickly. The semantic runtime layer must stay stable. Storage and audit must be boring, explicit, and reproducible.

