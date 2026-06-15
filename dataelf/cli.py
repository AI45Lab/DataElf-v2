from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from dataelf.config import DataElfConfig
from dataelf.connectors.ai_index_fixture import FixtureAIIndexConnector
from dataelf.stores.sqlite_store import SQLiteStore
from dataelf.tools.registry import list_tool_specs
from dataelf.workflow import run_task

app = typer.Typer(help="DataElf M1 CLI demo")
task_app = typer.Typer(help="Inspect task outputs")
tools_app = typer.Typer(help="Inspect DataElf tools")
app.add_typer(task_app, name="task")
app.add_typer(tools_app, name="tools")
console = Console()


def _config() -> DataElfConfig:
    return DataElfConfig.from_env()


def _store(config: DataElfConfig) -> SQLiteStore:
    store = SQLiteStore(config.sqlite_path)
    store.init_schema()
    return store


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", force=True)


@app.command()
def init() -> None:
    """Initialize the local DataElf workspace."""
    config = _config()
    config.ensure_dirs()
    store = _store(config)
    store.close()
    console.print(f"Initialized DataElf workspace: [bold]{config.workspace_dir.resolve()}[/bold]")
    console.print(f"SQLite: {config.sqlite_path.resolve()}")
    console.print(f"Raw cache: {config.raw_dir.resolve()}")


@app.command()
def seed(fixtures_dir: Path = typer.Argument(Path("fixtures/ai_index"))) -> None:
    """Validate fixture data and record fixture source metadata."""
    config = _config()
    config.fixtures_dir = fixtures_dir
    config.ensure_dirs()
    store = _store(config)
    connector = FixtureAIIndexConnector(fixtures_dir)
    counts = connector.validate()
    store.add_trace_event("fixture_seed", "fixture_seeded", {"fixtures_dir": str(fixtures_dir), "counts": counts})
    store.close()
    console.print(f"Seeded fixture metadata from [bold]{fixtures_dir}[/bold]")
    console.print(counts)


@app.command()
def run(query: str) -> None:
    """Run a DataElf research task."""
    _setup_logging()
    config = _config()
    try:
        task_state = run_task(query, config)
    except Exception as exc:
        console.print(f"[red]DataElf run failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    store = _store(config)
    report = store.get_latest_report(task_state.task_id)
    evidence = store.list_evidence(task_state.task_id)
    top_line = ""
    for item in evidence:
        if "OpenAgent Lab" in item.summary or item.payload.get("name") == "OpenAgent Lab":
            top_line = "Top institution: OpenAgent Lab"
            break
    console.print(f"[green]Task completed:[/green] {task_state.task_id}")
    if top_line:
        console.print(top_line)
    if report:
        console.print(f"Report: dataelf task report {task_state.task_id}")
    console.print(f"Evidence: dataelf task evidence {task_state.task_id}")
    console.print(f"Trace: dataelf task trace {task_state.task_id}")
    store.close()


@task_app.command("logs")
def task_logs(task_id: str) -> None:
    """Show workflow and runtime trace events for a task."""
    store = _store(_config())
    events = store.list_trace_events(task_id)
    table = Table(title=f"Logs: {task_id}")
    table.add_column("time")
    table.add_column("event")
    table.add_column("payload")
    for event in events:
        table.add_row(event["created_at"], event["event_type"], str(event["payload"]))
    console.print(table)
    store.close()


@task_app.command("evidence")
def task_evidence(task_id: str) -> None:
    """Show evidence items for a task."""
    store = _store(_config())
    evidence = store.list_evidence(task_id)
    table = Table(title=f"Evidence: {task_id}")
    table.add_column("evidence_id")
    table.add_column("type")
    table.add_column("title")
    table.add_column("summary")
    table.add_column("source_ids")
    for item in evidence:
        table.add_row(item.evidence_id, item.evidence_type, item.title, item.summary, ", ".join(item.source_ids))
    console.print(table)
    store.close()


@task_app.command("report")
def task_report(task_id: str) -> None:
    """Show the final markdown report for a task."""
    store = _store(_config())
    report = store.get_latest_report(task_id)
    if not report:
        console.print(f"[yellow]No report found for task:[/yellow] {task_id}")
    else:
        console.print(report.markdown)
    store.close()


@task_app.command("trace")
def task_trace(task_id: str) -> None:
    """Show DataElf tool calls for a task."""
    store = _store(_config())
    calls = store.list_tool_calls(task_id)
    table = Table(title=f"Tool Trace: {task_id}")
    table.add_column("tool")
    table.add_column("status")
    table.add_column("started_at")
    table.add_column("ended_at")
    table.add_column("error")
    for call in calls:
        table.add_row(call["tool_name"], call["status"], call["started_at"], call["ended_at"] or "", call["error"] or "")
    console.print(table)
    store.close()


@tools_app.command("list")
def tools_list() -> None:
    """List DataElf controlled tools."""
    table = Table(title="DataElf Tools")
    table.add_column("name")
    table.add_column("permission")
    table.add_column("description")
    for spec in list_tool_specs():
        table.add_row(spec.name, spec.permission, spec.description)
    console.print(table)
