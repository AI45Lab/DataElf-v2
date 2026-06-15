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
from dataelf.domains.ai_index.table_builder import read_table
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

