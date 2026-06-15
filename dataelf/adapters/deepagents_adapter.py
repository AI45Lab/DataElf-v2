from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dataelf.config import apply_llm_env_aliases, validate_model_env
from dataelf.schemas import TaskState, now_utc
from dataelf.tools.ai_index_tools import build_deepagents_tools
from dataelf.tools.runtime import ToolRuntime

logger = logging.getLogger("dataelf")

SYSTEM_PROMPT = """You are DataElf AutoResearch, a research planning and analysis agent for AI science intelligence.

You must use DataElf tools to access data, model records, analyze trends, write evidence, and draft reports.
You are not allowed to invent data.
You are not allowed to claim a conclusion unless you have first written evidence with write_evidence.
You are not allowed to produce a final report unless you call draft_report.

Your job:
1. Understand the user's research task.
2. Search relevant AI Index fixture records.
3. Fetch enough institution, paper, and scholar records.
4. Model records into domain objects and relations.
5. Analyze institution hotness growth in the AI Agent field for the half-year window.
6. Write evidence for the ranking result and supporting signals.
7. Draft a concise markdown report with explicit claims and evidence IDs.

For the target query "分析最近半年 AI Agent 领域热度上升最快的机构，并给出证据", you should produce:
- a ranked list of top institutions by hotness growth;
- at least three evidence items for the top institution;
- at least two explicit claims;
- a final markdown report.

Keep tool calls compact and purposeful. Prefer structured outputs. Do not call tools unrelated to the task.
"""


class DeepAgentsAdapter:
    def __init__(self, runtime: ToolRuntime, model: str, skills_dir: Path | None = None):
        self.runtime = runtime
        self.model = model
        self.skills_dir = skills_dir

    def run(self, task_state: TaskState) -> TaskState:
        apply_llm_env_aliases()
        validate_model_env(self.model)
        try:
            from deepagents import create_deep_agent
        except ImportError as exc:
            raise RuntimeError("deepagents is not installed. Run `uv pip install -e .` or `pip install -e .`.") from exc

        logger.info("autoresearch start: task=%s model=%s", task_state.task_id, self.model)
        self.runtime.store.add_trace_event(task_state.task_id, "autoresearch_start", {"model": self.model})
        tools = build_deepagents_tools(self.runtime, task_state.task_id)
        agent = create_deep_agent(
            model=self._deepagents_model(),
            tools=tools,
            system_prompt=self._system_prompt(),
        )
        result = agent.invoke({"messages": [{"role": "user", "content": self._user_prompt(task_state)}]})
        self.runtime.store.add_trace_event(task_state.task_id, "autoresearch_result", {"result_type": type(result).__name__})

        evidence = self.runtime.store.list_evidence(task_state.task_id)
        claims = self.runtime.store.list_claims(task_state.task_id)
        report = self.runtime.store.get_latest_report(task_state.task_id)
        if not evidence:
            raise RuntimeError("DeepAgentsAdapter finished but no evidence was written. The agent must call write_evidence.")
        if report is None:
            raise RuntimeError("DeepAgentsAdapter finished but no report was drafted. The agent must call draft_report.")
        task_state.evidence_ids = [item.evidence_id for item in evidence]
        task_state.claim_ids = [claim.claim_id for claim in claims]
        task_state.report_id = report.report_id
        task_state.tool_call_ids = [call["tool_call_id"] for call in self.runtime.store.list_tool_calls(task_state.task_id)]
        task_state.status = "completed"
        task_state.updated_at = now_utc()
        self.runtime.store.save_task_state(task_state)
        self.runtime.store.add_trace_event(task_state.task_id, "autoresearch_completed", {"report_id": report.report_id})
        logger.info("autoresearch completed: task=%s report=%s", task_state.task_id, report.report_id)
        return task_state

    def _system_prompt(self) -> str:
        extra = ""
        if self.skills_dir:
            skill_path = self.skills_dir / "ai_index_research.md"
            if skill_path.exists():
                extra = "\n\nAdditional DataElf skill guidance:\n" + skill_path.read_text(encoding="utf-8")
        return SYSTEM_PROMPT + extra

    def _deepagents_model(self) -> Any:
        if self.model.startswith("openai:"):
            try:
                from langchain.chat_models import init_chat_model
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAI-compatible models require langchain-openai. "
                    "Run `pip install langchain-openai` or reinstall this project."
                ) from exc
            return init_chat_model(self.model, use_responses_api=False)
        return self.model

    def _user_prompt(self, task_state: TaskState) -> str:
        return (
            f"User query: {task_state.user_query}\n"
            f"Task id: {task_state.task_id}\n"
            "Domain: AI Index science intelligence\n"
            "Available fixture domain: scholars, papers, institutions\n"
            "Required output: save a report using draft_report, with evidence IDs."
        )
