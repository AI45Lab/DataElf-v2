from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from dataelf.domains.ai_index.client import AIIndexClient
from dataelf.domains.ai_index.table_builder import read_table
from dataelf.schemas import DiscoveryJob


class InsightsExplorerAdapter(Protocol):
    # Adapter boundary for the single insights_explore implementation.
    # TODO: If the team replaces DeepAgentsCode with another framework, keep this
    # method contract and update the concrete adapter below instead of changing
    # the outer DiscoveryWorkflow.
    def run(self, job: DiscoveryJob, context: dict[str, Any]) -> DiscoveryJob:
        ...


class DeepAgentsCodeInsightsExplorer:
    """M1 adapter shell.

    The production DeepAgentsCode integration will replace the deterministic
    scaffold below. Keeping the adapter boundary now lets intern A work on the
    explorer without changing the outer DiscoveryWorkflow.
    """

    def __init__(self, client: AIIndexClient):
        self.client = client

    def run(self, job: DiscoveryJob, context: dict[str, Any]) -> DiscoveryJob:
        workspace_path = Path(job.workspace_path)
        scope = job.scope
        expected_outputs = int(scope.get("expected_outputs", 3))
        topic = str(scope.get("topic") or "Agentic LLMs")
        sub_domains = scope.get("sub_domains") or ["Agentic LLMs"]
        domains = scope.get("domains") or ["LLMs"]

        papers = self.client.search_papers(sub_domains=sub_domains, domains=domains, sort_type="heat", page=1, size=50)
        if _total(papers) == 0:
            papers = self.client.search_papers(sub_domains=["AI Agent"], sort_type="heat", page=1, size=50)
        institutions = self.client.search_institutions(sub_domains=sub_domains, domains=domains, sort_type="index", page=1, size=50)
        if _total(institutions) == 0:
            institutions = self.client.search_institutions(sub_domains=["AI Agent"], sort_type="index", page=1, size=50)
        scholars = self.client.search_scholars(sub_domains=sub_domains, domains=domains, page=1, size=50)
        if _total(scholars) == 0:
            scholars = self.client.search_scholars(sub_domains=["AI Agent"], page=1, size=50)

        institution_rows = read_table(workspace_path, "institutions")
        for row in institution_rows[:3]:
            institution_id = row.get("institution_id")
            if institution_id:
                self.client.fetch_institution_funding(institution_id)

        self._write_analysis_script(workspace_path)
        candidate_signals = self._build_candidate_signals(workspace_path, topic)
        insights = self._build_insights(workspace_path, topic, candidate_signals, expected_outputs)
        _write_json(workspace_path / "insights" / "candidate_signals.json", {"candidate_signals": candidate_signals})
        _write_json(workspace_path / "insights" / "insight_candidates.json", {"insight_candidates": insights})
        (workspace_path / "insights" / "final_brief.md").write_text(
            self._render_brief(topic, insights, context.get("domain_pack", {})),
            encoding="utf-8",
        )
        (workspace_path / "notes" / "research_plan.md").write_text(
            "\n".join(
                [
                    "# Research Plan",
                    "",
                    f"- Seed query: {job.seed_query}",
                    f"- Topic: {topic}",
                    "- Breadth scan: AI Index papers, institutions, scholars, and funding tables.",
                    "- Code analysis: scripts/analyze_institution_growth.py is ready for iterative extension.",
                    "- Web investigation: reserved for configured web_search/fetch_url provider.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        job.insight_candidate_ids = [item["insight_id"] for item in insights]
        return job

    def _build_candidate_signals(self, workspace_path: Path, topic: str) -> list[dict[str, Any]]:
        institutions = _sorted_by_growth(read_table(workspace_path, "institutions"))
        papers = read_table(workspace_path, "papers")
        top = institutions[0] if institutions else {}
        eval_papers = [
            row
            for row in papers
            if any(term in (row.get("title", "") + " " + row.get("abstract", "")).lower() for term in ["benchmark", "evaluation", "tool"])
        ]
        signals = [
            {
                "signal_id": "sig_001",
                "signal_type": "institution_momentum_anomaly",
                "summary": f"{top.get('name', 'A leading institution')} shows concentrated recent momentum in {topic}.",
                "why_might_matter": "Institution-level momentum can reveal where research capability, talent, and deployment focus are converging before it appears in slower citation metrics.",
                "supporting_tables": ["institutions.csv", "papers.csv", "funding.csv"],
                "related_entities": ["Institution", "Paper", "FundingEvent", "Topic"],
                "suggested_deep_dive": [
                    "Compare heat growth against paper_count to avoid pure scale effects",
                    "Check whether growth is driven by multiple papers instead of one outlier",
                    "Join funding signals with publication momentum",
                ],
                "initial_score": {"novelty": 0.62, "magnitude": 0.72, "strategic_relevance": 0.78},
                "status": "needs_deep_dive",
            },
            {
                "signal_id": "sig_002",
                "signal_type": "evaluation_toolchain_cluster",
                "summary": f"{len(eval_papers)} papers in the workspace mention benchmark, evaluation, or tool-use signals.",
                "why_might_matter": "Agentic LLM competition may be shifting from raw model claims toward evaluation harnesses, tool reliability, and operational constraints.",
                "supporting_tables": ["papers.csv", "paper_author.csv", "paper_institution.csv"],
                "related_entities": ["Paper", "Scholar", "Institution", "Topic"],
                "suggested_deep_dive": [
                    "Extract recurring benchmark names",
                    "Map which institutions repeatedly publish evaluation/tooling papers",
                    "Add external web validation for benchmark adoption",
                ],
                "initial_score": {"novelty": 0.7, "magnitude": 0.58, "strategic_relevance": 0.84},
                "status": "needs_deep_dive",
            },
        ]
        return signals

    def _build_insights(
        self,
        workspace_path: Path,
        topic: str,
        signals: list[dict[str, Any]],
        expected_outputs: int,
    ) -> list[dict[str, Any]]:
        institutions = _sorted_by_growth(read_table(workspace_path, "institutions"))
        papers = read_table(workspace_path, "papers")
        top_name = institutions[0].get("name", "the leading institution") if institutions else "the leading institution"
        top_growth = institutions[0].get("absolute_growth", "") if institutions else ""
        insights = [
            {
                "insight_id": "ins_001",
                "title": f"{topic} momentum is clustering around institution-level execution capacity",
                "thesis": f"{top_name} combines recent heat growth, paper activity, and available funding context, suggesting the opportunity is not just a paper ranking but an execution-capacity cluster.",
                "why_now": "The last-six-month heat fields and recent publication dates appear together in the workspace tables, making this a near-term signal rather than a static reputation measure.",
                "supporting_signals": ["sig_001"],
                "analysis_artifacts": [
                    "scripts/analyze_institution_growth.py",
                    "domains/ai_index/tables/institutions.csv",
                    "domains/ai_index/tables/papers.csv",
                    "domains/ai_index/tables/funding.csv",
                ],
                "related_entities": [f"Institution:{top_name}", f"Topic:{topic}"],
                "external_support": [],
                "counterarguments": [
                    "Fixture/API heat may reflect media attention rather than durable research advantage.",
                    "A small number of high-heat papers can overstate institution-level breadth.",
                    "External web validation is pending until a web search provider is configured.",
                ],
                "confidence": 0.66,
                "next_questions": [
                    "Check whether the same institutions also gain citation velocity over 12 months.",
                    "Verify funding and product/news signals through web_search once configured.",
                ],
            },
            {
                "insight_id": "ins_002",
                "title": f"{topic} differentiation is leaning toward evaluation and toolchain infrastructure",
                "thesis": "The paper table contains repeated benchmark, evaluation, and tool-use language, pointing to a shift from model novelty alone toward measurable agent reliability and operating constraints.",
                "why_now": "Recent AI Index paper rows concentrate around tool-use and benchmark/evaluation terms, matching the practical pressure to compare agent systems beyond demos.",
                "supporting_signals": ["sig_002"],
                "analysis_artifacts": [
                    "domains/ai_index/tables/papers.csv",
                    "domains/ai_index/tables/paper_author.csv",
                    "domains/ai_index/tables/paper_institution.csv",
                ],
                "related_entities": [f"Topic:{topic}", "Entity:Benchmark", "Entity:Toolchain", "Entity:Paper"],
                "external_support": [],
                "counterarguments": [
                    "Keyword spotting can miss papers that discuss evaluation using different terminology.",
                    "Benchmark mentions do not prove adoption without external GitHub, leaderboard, or citation evidence.",
                ],
                "confidence": 0.61,
                "next_questions": [
                    "Extract named benchmarks from abstracts and titles.",
                    "Join with web/GitHub sources to test whether benchmarks are being adopted.",
                ],
            },
        ]
        if expected_outputs >= 3 and papers:
            insights.append(
                {
                    "insight_id": "ins_003",
                    "title": f"{topic} may be broadening through multi-institution author networks",
                    "thesis": "The author and institution relation tables make it possible to test whether agentic research is spreading through collaboration networks instead of isolated lab announcements.",
                    "why_now": "The new workspace exposes paper-author and paper-institution joins, allowing the next analysis pass to distinguish isolated hot papers from repeatable collaboration patterns.",
                    "supporting_signals": ["sig_001", "sig_002"],
                    "analysis_artifacts": [
                        "domains/ai_index/tables/paper_author.csv",
                        "domains/ai_index/tables/paper_institution.csv",
                        "domains/ai_index/tables/scholars.csv",
                    ],
                    "related_entities": ["Entity:Scholar", "Entity:Institution", f"Topic:{topic}"],
                    "external_support": [],
                    "counterarguments": [
                        "M1 relation tables are lightweight and need entity mapping hardening.",
                        "Fixture data may underrepresent cross-affiliation and scholar mobility.",
                    ],
                    "confidence": 0.54,
                    "next_questions": [
                        "Ask intern B's mapper to dedupe institution and scholar identities.",
                        "Measure repeated collaborations across venues and time windows.",
                    ],
                }
            )
        if top_growth:
            insights[0]["thesis"] += f" Observed absolute heat growth in the current table is {top_growth}."
        return insights[: max(1, min(expected_outputs, 5))]

    def _write_analysis_script(self, workspace_path: Path) -> None:
        script = workspace_path / "scripts" / "analyze_institution_growth.py"
        script.write_text(
            """from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
institutions = pd.read_csv(ROOT / "domains/ai_index/tables/institutions.csv")
institutions["heat"] = pd.to_numeric(institutions["heat"], errors="coerce").fillna(0)
institutions["previous_heat"] = pd.to_numeric(institutions["previous_heat"], errors="coerce").fillna(0)
institutions["absolute_growth"] = institutions["heat"] - institutions["previous_heat"]
print(institutions.sort_values("absolute_growth", ascending=False).head(10))
""",
            encoding="utf-8",
        )

    def _render_brief(self, topic: str, insights: list[dict[str, Any]], domain_pack: dict[str, Any]) -> str:
        lines = [
            f"# Insight Discovery Brief: {topic}",
            "",
            f"Domain pack: {domain_pack.get('display_name', 'ai_index')}",
            "",
            "## Candidates",
        ]
        for item in insights:
            lines.extend(
                [
                    "",
                    f"### {item['insight_id']}: {item['title']}",
                    "",
                    item["thesis"],
                    "",
                    f"Why now: {item['why_now']}",
                    "",
                    f"Confidence: {item['confidence']}",
                    "",
                    "Counterarguments:",
                ]
            )
            lines.extend([f"- {text}" for text in item.get("counterarguments", [])])
        return "\n".join(lines) + "\n"


def _total(response: dict[str, Any]) -> int:
    data = response.get("data", {})
    if isinstance(data, dict):
        if "total" in data:
            return int(data.get("total") or 0)
        if isinstance(data.get("list"), list):
            return len(data["list"])
    return 0


def _sorted_by_growth(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        heat = _float(row.get("heat"))
        previous = _float(row.get("previous_heat"))
        item = dict(row)
        item["absolute_growth"] = round(heat - previous, 4)
        item["growth_rate"] = round((heat - previous) / previous, 4) if previous else None
        enriched.append(item)
    return sorted(enriched, key=lambda row: row.get("absolute_growth", 0), reverse=True)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
