from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dataelf.cli import app


def test_cli_init_and_seed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixtures = Path.cwd() / "fixtures" / "ai_index"
    fixtures.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "fixtures" / "ai_index"
    for name in ["institutions.json", "papers.json", "scholars.json", "schema_graph.yaml"]:
        (fixtures / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".dataelf" / "dataelf.sqlite").exists()

    result = runner.invoke(app, ["seed", str(fixtures)])
    assert result.exit_code == 0
    assert "institutions" in result.output
