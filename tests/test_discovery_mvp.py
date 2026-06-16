from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dataelf.cli import app
from dataelf.config import DEFAULT_AI_INDEX_API_KEY, DEFAULT_AI_INDEX_BASE_URL, DataElfConfig
from dataelf.discovery.domain_registry import DomainRegistry
from dataelf.discovery.quality_review import review_workspace
from dataelf.discovery.workflow import run_discovery
from dataelf.discovery.workspace import prepare_workspace
from dataelf.domains.ai_index.client import AIIndexClient
from dataelf.domains.ai_index.connector import AIIndexConnector, AI_INDEX_ENDPOINTS
from dataelf.domains.ai_index.table_builder import read_table, update_tables_from_response
from dataelf.stores.sqlite_store import SQLiteStore


def test_workspace_domain_pack_and_ai_index_client_fixture(tmp_path: Path) -> None:
    workspace = prepare_workspace(tmp_path / "workspace")
    pack = DomainRegistry().load_domain_pack("ai_index")
    assert pack["domain"] == "ai_index"
    assert "search_papers" in pack["tools"]

    connector = AIIndexConnector(mode="fixture", fixtures_dir=Path("fixtures/ai_index"), workspace_path=workspace)
    client = AIIndexClient(connector=connector, workspace_path=workspace)
    response = client.search_papers(sub_domains=["AI Agent"], sort_type="heat", page=1, size=5)

    assert response["endpoint"] == AI_INDEX_ENDPOINTS["search_papers"]
    assert (workspace / "raw" / "ai_index").exists()
    assert read_table(workspace, "papers")
    assert read_table(workspace, "paper_author")
    assert read_table(workspace, "paper_institution")
    assert (workspace / "domains" / "ai_index" / "tables" / "paper_yearly_counts.csv").exists()
    assert (workspace / "domains" / "ai_index" / "tables" / "paper_awards.csv").exists()

    client.search_scholars(sub_domains=["AI Agent"], sort_type="heat", page=1, size=5)
    client.search_institutions(sub_domains=["AI Agent"], sort_type="heat", page=1, size=5)
    client.fetch_institution_funding("inst_openagent_lab")

    assert read_table(workspace, "scholars")
    assert read_table(workspace, "scholar_institution")
    assert read_table(workspace, "scholar_venues")
    assert read_table(workspace, "institutions")
    assert read_table(workspace, "funding_summary")[0]["total_funding_value_usd"] == "50000000"
    assert read_table(workspace, "funding")
    assert (workspace / "domains" / "ai_index" / "tables" / "funding_investors.csv").exists()


def test_ai_index_table_builder_handles_openapi_shaped_entities(tmp_path: Path) -> None:
    workspace = prepare_workspace(tmp_path / "workspace")
    raw_uri = str(workspace / "raw" / "ai_index" / "sample.json")

    update_tables_from_response(
        workspace,
        {
            "endpoint": AI_INDEX_ENDPOINTS["search_papers"],
            "raw_uri": raw_uri,
            "data": {
                "list": [
                    {
                        "id": "paper_1",
                        "title": "Agent Benchmarks",
                        "first_authors": ["Alice Chen"],
                        "corresponding_authors": ["Bob Li"],
                        "institution_id": "inst_1",
                        "institution": "OpenAgent Lab",
                        "conference_name": "NeurIPS",
                        "conference_abbreviation": "NeurIPS",
                        "count_by_year": [{"year": 2026, "cited_by_count": 42}],
                        "conf_award_info": {"conf": "NeurIPS", "year": 2026, "awards": [{"key": "spotlight", "title": "Spotlight"}]},
                    }
                ]
            },
        },
    )
    update_tables_from_response(
        workspace,
        {
            "endpoint": AI_INDEX_ENDPOINTS["search_institutions"],
            "raw_uri": raw_uri,
            "data": {
                "list": [
                    {
                        "id": "inst_1",
                        "name": "OpenAgent Lab",
                        "country_code": "US",
                        "conference_names": ["NeurIPS"],
                        "journal_names": ["Nature Machine Intelligence"],
                        "award_list": [{"conf": "NeurIPS", "year": 2026, "awards": [{"key": "best", "title": "Best Paper"}]}],
                        "index_radar_display": {"academic_impact": 91, "capital_signal": 80, "total_score": 88},
                    }
                ]
            },
        },
    )
    update_tables_from_response(
        workspace,
        {
            "endpoint": AI_INDEX_ENDPOINTS["search_scholars"],
            "raw_uri": raw_uri,
            "data": {
                "list": [
                    {
                        "id": "scholar_1",
                        "display_name": "Alice Chen",
                        "institution_id": "inst_1",
                        "institution": "OpenAgent Lab",
                        "count_by_year": [{"year": 2026, "cited_by_count": 12}],
                        "conference_names": ["NeurIPS"],
                        "award_list": [{"conf": "NeurIPS", "year": 2026, "awards": [{"key": "oral", "title": "Oral"}]}],
                    }
                ]
            },
        },
    )
    update_tables_from_response(
        workspace,
        {
            "endpoint": AI_INDEX_ENDPOINTS["fetch_institution_funding"].format(institution_id="inst_1"),
            "request": {"institution_id": "inst_1"},
            "raw_uri": raw_uri,
            "data": {
                "summary": {"total_funding": {"currency": "USD", "value": 100, "value_usd": 100}, "funding_round_count": 1},
                "funding": {
                    "financials_highlights": {"num_investors": 2, "num_lead_investors": 1},
                    "funding_rounds": [
                        {
                            "id": "round_1",
                            "uuid": "uuid_1",
                            "title": "Seed Round",
                            "announced_on": "2026-01-01",
                            "money_raised": {"currency": "USD", "value": 100, "value_usd": 100},
                            "lead_investors": [{"id": "investor_1", "value": "Example Capital"}],
                        }
                    ],
                    "investors": [
                        {
                            "id": "record_1",
                            "type": "investment",
                            "lead_investor": True,
                            "funding_round": {"id": "round_1", "value": "Seed Round"},
                            "investor": {"id": "investor_1", "value": "Example Capital", "type": "organization"},
                        }
                    ],
                },
                "invested": {"investments": []},
            },
        },
    )

    assert read_table(workspace, "paper_yearly_counts")[0]["cited_by_count"] == "42"
    assert read_table(workspace, "paper_awards")[0]["award_title"] == "Spotlight"
    assert read_table(workspace, "institution_venues")[0]["venue_name"] == "NeurIPS"
    assert read_table(workspace, "institution_awards")[0]["award_title"] == "Best Paper"
    assert read_table(workspace, "scholar_yearly_counts")[0]["year"] == "2026"
    assert read_table(workspace, "scholar_awards")[0]["award_key"] == "oral"
    assert read_table(workspace, "funding_rounds")[0]["funding_id"] == "round_1"
    assert read_table(workspace, "funding_investors")[0]["investor_name"] == "Example Capital"


def test_discovery_workflow_creates_job_workspace_and_review(tmp_path: Path) -> None:
    config = DataElfConfig(
        workspace_dir=tmp_path / ".dataelf",
        sqlite_path=tmp_path / ".dataelf" / "dataelf.sqlite",
        raw_dir=tmp_path / ".dataelf" / "raw",
        workspaces_dir=tmp_path / ".dataelf" / "workspaces",
        fixtures_dir=Path("fixtures/ai_index"),
        ai_index_mode="fixture",
    )
    job = run_discovery("围绕 Agentic LLMs，基于 AI Index 和联网搜索，发现最近值得关注的 3 个 insight", config)

    workspace = Path(job.workspace_path)
    assert job.status == "completed"
    assert job.trigger_type == "user"
    assert job.insight_candidate_ids
    assert (workspace / "insights" / "candidate_signals.json").exists()
    assert (workspace / "insights" / "insight_candidates.json").exists()
    assert (workspace / "insights" / "final_brief.md").exists()
    assert read_table(workspace, "institutions")

    review = json.loads((workspace / "reviews" / "quality_review.json").read_text(encoding="utf-8"))
    assert review["review_status"] in {"pass", "pass_with_warnings"}
    store = SQLiteStore(config.sqlite_path)
    store.init_schema()
    assert store.get_discovery_job(job.job_id) is not None
    assert store.get_latest_quality_review(job.job_id) is not None
    store.close()


def test_quality_review_detects_missing_candidates(tmp_path: Path) -> None:
    workspace = prepare_workspace(tmp_path / "workspace")
    (workspace / "insights" / "insight_candidates.json").write_text('{"insight_candidates":[]}\n', encoding="utf-8")
    review = review_workspace("job_test", workspace)
    assert review.review_status == "failed"
    assert review.recommended_revision


def test_cli_discover_smoke(tmp_path: Path, monkeypatch) -> None:
    fixtures = tmp_path / "fixtures" / "ai_index"
    fixtures.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "fixtures" / "ai_index"
    for name in ["institutions.json", "papers.json", "scholars.json", "schema_graph.yaml"]:
        (fixtures / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("DATAELF_WORKSPACE", str(tmp_path / ".dataelf"))
    monkeypatch.setenv("DATAELF_FIXTURES_DIR", str(fixtures))
    monkeypatch.setenv("DATAELF_AI_INDEX_MODE", "fixture")

    result = CliRunner().invoke(
        app,
        ["discover", "围绕 Agentic LLMs，基于 AI Index 和联网搜索，发现最近值得关注的 3 个 insight"],
    )

    assert result.exit_code == 0
    assert "Discovery job completed" in result.output
    assert (tmp_path / ".dataelf" / "workspaces").exists()


def test_ai_index_api_defaults_match_provided_curl() -> None:
    assert DEFAULT_AI_INDEX_BASE_URL == "https://index.shlab.org.cn/api/v2"
    assert DEFAULT_AI_INDEX_API_KEY == "ak_0XWHy2OQpSKnaKHL"
    assert AI_INDEX_ENDPOINTS["fetch_institution_funding"] == "/openapi/institutions/{institution_id}/funding-profile"
