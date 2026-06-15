from __future__ import annotations

import sys
import types
from pathlib import Path

from dataelf.adapters.deepagents_adapter import DeepAgentsAdapter
from dataelf.config import DataElfConfig
from dataelf.connectors.ai_index_fixture import FixtureAIIndexConnector
from dataelf.schemas import TaskState
from dataelf.stores.raw_cache import RawCache
from dataelf.stores.sqlite_store import SQLiteStore
from dataelf.tools.runtime import ToolRuntime


def test_deepagents_adapter_uses_dataelf_tool_wrappers(monkeypatch, tmp_path: Path) -> None:
    class FakeAgent:
        def __init__(self, tools):
            self.tools = {tool.__name__: tool for tool in tools}

        def invoke(self, payload):
            inst = self.tools["search_records"]("institution", "AI Agent", "half_year")
            papers = self.tools["search_records"]("paper", "AI Agent", "half_year")
            scholars = self.tools["search_records"]("scholar", "AI Agent", "half_year")
            fetched = self.tools["fetch_records"]("institution", inst["record_ids"][:4])
            all_record_ids = inst["record_ids"] + papers["record_ids"] + scholars["record_ids"]
            self.tools["model_records"](all_record_ids)
            trend = self.tools["analyze_trend"]("AI Agent", "institution_hotness_growth", "half_year", 5)
            top = trend["ranking"][0]
            paper_ids = fetched["details"][0]["related_paper_ids"]
            scholar_ids = fetched["details"][0]["related_scholar_ids"]
            e1 = self.tools["write_evidence"](
                "机构半年热度增长",
                "metric",
                f"{top['name']} 半年热度从 {top['previous_hotness']} 升至 {top['current_hotness']}，增长率 {top['growth_rate']}。",
                top,
                top["supporting_record_ids"] + top["supporting_object_ids"],
            )
            e2 = self.tools["write_evidence"](
                "AI Agent 论文热度增长",
                "aggregate",
                f"{top['name']} 关联论文 {', '.join(paper_ids[:3])} 在最近半年贡献明显热度。",
                {"paper_ids": paper_ids},
                [f"rec_{task_id}_paper_{paper_id}" for paper_id in paper_ids[:3]],
            )
            e3 = self.tools["write_evidence"](
                "学者与新闻活跃度信号",
                "aggregate",
                f"{top['name']} 关联学者 {', '.join(scholar_ids[:3])} 及新闻发布共同支撑趋势。",
                {"scholar_ids": scholar_ids},
                [f"rec_{task_id}_scholar_{scholar_id}" for scholar_id in scholar_ids[:3]],
            )
            evidence_ids = [e1["evidence_id"], e2["evidence_id"], e3["evidence_id"]]
            markdown = "\n".join(
                [
                    "# 最近半年 AI Agent 领域热度上升最快的机构分析",
                    "",
                    "## 结论",
                    f"- 结论 1：{top['name']} 是最近半年 AI Agent 领域热度上升最快的机构。[{e1['evidence_id']}]",
                    f"- 结论 2：论文、学者和新闻信号共同支持该结论。[{e2['evidence_id']}, {e3['evidence_id']}]",
                    "",
                    "## 排名",
                    "| 排名 | 机构 | 半年热度 | 上一半年热度 | 增长量 | 增长率 |",
                    "|---|---|---:|---:|---:|---:|",
                    f"| 1 | {top['name']} | {top['current_hotness']} | {top['previous_hotness']} | {top['absolute_growth']} | {top['growth_rate']} |",
                    "",
                    "## 证据链",
                    f"### {e1['evidence_id']}: 机构半年热度增长",
                    "见 Evidence Store。",
                    f"### {e2['evidence_id']}: AI Agent 论文热度增长",
                    "见 Evidence Store。",
                    f"### {e3['evidence_id']}: 学者与新闻活跃度信号",
                    "见 Evidence Store。",
                    "",
                    "## 方法说明",
                    "本报告基于 AI Index fixture 数据，模拟学者库、论文库、机构库及其关联字段。当前结果不代表真实 AI Index 线上数据。",
                    "",
                    "## 限制",
                    "- 当前使用 mock fixture，不是线上 API。",
                    "- 热度指标为模拟字段。",
                    "- Verifier 当前只检查 claim-evidence coverage，不做真实事实裁判。",
                ]
            )
            self.tools["draft_report"](
                "最近半年 AI Agent 领域热度上升最快的机构分析",
                [
                    {"text": f"{top['name']} 是最近半年 AI Agent 领域热度上升最快的机构。", "evidence_ids": [e1["evidence_id"]]},
                    {"text": "论文、学者和新闻信号共同支持该结论。", "evidence_ids": [e2["evidence_id"], e3["evidence_id"]]},
                ],
                evidence_ids,
                markdown,
            )
            return {"messages": payload["messages"]}

    def create_deep_agent(model, tools, system_prompt):
        assert getattr(model, "model_name", None) == "test-model"
        assert any(tool.__name__ == "search_records" for tool in tools)
        assert "You must use DataElf tools" in system_prompt
        return FakeAgent(tools)

    fake_module = types.SimpleNamespace(create_deep_agent=create_deep_agent)
    monkeypatch.setitem(sys.modules, "deepagents", fake_module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    global task_id
    task_id = "task_contract"
    config = DataElfConfig(workspace_dir=tmp_path / ".dataelf", sqlite_path=tmp_path / ".dataelf/dataelf.sqlite", raw_dir=tmp_path / ".dataelf/raw", model="openai:test-model")
    store = SQLiteStore(config.sqlite_path)
    store.init_schema()
    runtime = ToolRuntime(store, RawCache(config.raw_dir), FixtureAIIndexConnector(Path("fixtures/ai_index")))
    state = TaskState(task_id=task_id, user_query="分析最近半年 AI Agent 领域热度上升最快的机构，并给出证据", status="running")
    store.save_task_state(state)

    final_state = DeepAgentsAdapter(runtime=runtime, model=config.model, skills_dir=Path("skills")).run(state)

    assert final_state.report_id is not None
    assert len(store.list_tool_calls(task_id)) >= 8
    assert len(store.list_evidence(task_id)) == 3
    assert store.get_latest_report(task_id) is not None
    assert any(call["tool_name"] == "draft_report" for call in store.list_tool_calls(task_id))
    store.close()
