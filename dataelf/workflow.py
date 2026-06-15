from __future__ import annotations

import logging
from typing import Any, TypedDict

from dataelf.adapters.deepagents_adapter import DeepAgentsAdapter
from dataelf.config import DataElfConfig
from dataelf.connectors.ai_index_fixture import FixtureAIIndexConnector
from dataelf.schemas import TaskState, new_id, now_utc
from dataelf.stores.raw_cache import RawCache
from dataelf.stores.sqlite_store import SQLiteStore
from dataelf.tools.runtime import ToolRuntime
from dataelf.verifier.evidence_verifier import verify_report

logger = logging.getLogger("dataelf")


class DataElfWorkflowState(TypedDict, total=False):
    user_query: str
    config: DataElfConfig
    store: SQLiteStore
    runtime: ToolRuntime
    task_state: TaskState


def initialize_task(user_query: str, store: SQLiteStore) -> TaskState:
    task_state = TaskState(task_id=new_id("task"), user_query=user_query, status="running")
    store.save_task_state(task_state)
    store.add_trace_event(task_state.task_id, "task_initialized", {"user_query": user_query})
    logger.info("workflow init_task: %s", task_state.task_id)
    return task_state

# TODO: replace this part with rule + llm(?)
def parse_intent_minimal(task_state: TaskState, store: SQLiteStore) -> TaskState:
    query = task_state.user_query
    intent: dict[str, Any] = {}
    if "AI Agent" in query or "agent" in query.lower():
        intent["field"] = "AI Agent"
    if "最近半年" in query or "半年" in query:
        intent["time_window"] = "half_year"
    if "机构" in query and "热度上升最快" in query:
        intent["target"] = "institution_hotness_growth"
    task_state.intent = intent
    task_state.updated_at = now_utc()
    store.save_task_state(task_state)
    store.add_trace_event(task_state.task_id, "intent_parse", {"intent": intent})
    logger.info("workflow intent_parse: %s", intent)
    return task_state


def run_task(user_query: str, config: DataElfConfig) -> TaskState:
    config.ensure_dirs()
    graph = build_workflow()
    result = graph.invoke({"user_query": user_query, "config": config})
    return result["task_state"]


def build_workflow():
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError("langgraph is not installed. Run `uv pip install -e .` or `pip install -e .`.") from exc

    def prepare(state: dict[str, Any]) -> dict[str, Any]:
        config: DataElfConfig = state["config"]
        store = SQLiteStore(config.sqlite_path)
        store.init_schema()
        connector = FixtureAIIndexConnector(config.fixtures_dir)
        runtime = ToolRuntime(store, RawCache(config.raw_dir), connector)
        return {"store": store, "runtime": runtime}

    def init_task_node(state: dict[str, Any]) -> dict[str, Any]:
        return {"task_state": initialize_task(state["user_query"], state["store"])}

    def intent_node(state: dict[str, Any]) -> dict[str, Any]:
        return {"task_state": parse_intent_minimal(state["task_state"], state["store"])}

    def autoresearch_node(state: dict[str, Any]) -> dict[str, Any]:
        config: DataElfConfig = state["config"]
        adapter = DeepAgentsAdapter(runtime=state["runtime"], model=config.model, skills_dir=config.skills_dir)
        return {"task_state": adapter.run(state["task_state"])}

    def verify_node(state: dict[str, Any]) -> dict[str, Any]:
        logger.info("workflow evidence_verify: %s", state["task_state"].task_id)
        return {"task_state": verify_report(state["task_state"], state["store"])}

    workflow = StateGraph(DataElfWorkflowState)
    workflow.add_node("prepare", prepare)
    workflow.add_node("init_task", init_task_node)
    workflow.add_node("intent_parse", intent_node)
    workflow.add_node("auto_research", autoresearch_node)
    workflow.add_node("evidence_verify", verify_node)
    workflow.set_entry_point("prepare")
    workflow.add_edge("prepare", "init_task")
    workflow.add_edge("init_task", "intent_parse")
    workflow.add_edge("intent_parse", "auto_research")
    workflow.add_edge("auto_research", "evidence_verify")
    workflow.add_edge("evidence_verify", END)
    return workflow.compile()
