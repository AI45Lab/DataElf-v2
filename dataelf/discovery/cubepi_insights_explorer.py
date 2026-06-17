from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from dataelf.discovery.base import DiscoveryContext, DiscoveryResult
from dataelf.discovery.cubepi_prompt_builder import write_cubepi_prompt
from dataelf.discovery.cubepi_tools import CubePiWorkspaceTools
from dataelf.discovery.result_parser import parse_discovery_result
from dataelf.schemas import DiscoveryJob

logger = logging.getLogger("dataelf.discovery.cubepi")


class CubePiInsightsExplorer:
    """Experimental CubePi-backed insights explorer.

    This is an Option 2 comparison spike. It must not replace or affect the
    default DeepAgentsCode runner.
    """

    def run(self, job: DiscoveryJob, context: DiscoveryContext) -> DiscoveryResult:
        workspace_path = Path(context.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        logs_dir = workspace_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = write_cubepi_prompt(job, context)
        logger.info("CubePi prompt written: %s", prompt_path)

        tools = CubePiWorkspaceTools(workspace_path, context)
        if _env_bool("DATAELF_CUBEPI_DRY_RUN", False) or bool(context.config.get("cubepi_dry_run")):
            logger.info("Running CubePi explorer in dry-run mode.")
            _write_dry_run_artifacts(job, workspace_path, tools)
            return parse_discovery_result(workspace_path, job_id=job.job_id)

        try:
            cubepi = importlib.import_module("cubepi")
        except ImportError:
            message = "CubePi is not installed. Install it with `uv pip install cubepi` or install the optional DataElf cubepi extra, then retry with DATAELF_INSIGHTS_EXPLORER=cubepi."
            (logs_dir / "cubepi_error.log").write_text(message + "\n", encoding="utf-8")
            return DiscoveryResult(job_id=job.job_id, status="failed", workspace_path=str(workspace_path), warnings=[message], error=message)

        prompt = prompt_path.read_text(encoding="utf-8")
        try:
            output = _run_cubepi_agent(cubepi, prompt, tools, context)
            (logs_dir / "cubepi_stdout.log").write_text(str(output or ""), encoding="utf-8")
        except Exception as exc:
            message = f"CubePi run failed: {exc}"
            (logs_dir / "cubepi_error.log").write_text(message + "\n", encoding="utf-8")
            result = parse_discovery_result(workspace_path, job_id=job.job_id)
            if result.status != "completed":
                result.error = "cubepi_run_failed"
                result.warnings.append(message)
            return result

        return parse_discovery_result(workspace_path, job_id=job.job_id)


def _run_cubepi_agent(cubepi: Any, prompt: str, tools: CubePiWorkspaceTools, context: DiscoveryContext) -> Any:
    tool_functions = _build_tool_functions(cubepi, tools)
    model = os.getenv("DATAELF_CUBEPI_MODEL") or context.config.get("cubepi_model") or context.model or os.getenv("DATAELF_MODEL")
    provider = os.getenv("DATAELF_CUBEPI_PROVIDER") or context.config.get("cubepi_provider")
    agent_cls = _find_agent_class(cubepi)
    if agent_cls is None:
        raise RuntimeError("Installed cubepi package does not expose a recognized Agent/Pi class. Update CubePiInsightsExplorer for this CubePi version.")
    bound_model = _build_bound_model(cubepi, provider=provider, model=model)
    agent = agent_cls(model=bound_model, system_prompt="You are DataElf CubePi insights_explorer.", tools=tool_functions)
    prompt_method = getattr(agent, "prompt", None)
    if not callable(prompt_method):
        raise RuntimeError("CubePi Agent does not expose prompt(...).")
    max_rounds = _env_int("DATAELF_CUBEPI_MAX_ROUNDS", 3)
    run_ids: list[str] = []
    current_prompt = prompt
    final_result = None
    for attempt in range(1, max_rounds + 1):
        run_ids.append(asyncio.run(prompt_method(current_prompt)))
        final_result = parse_discovery_result(tools.workspace_path)
        if final_result.status == "completed":
            break
        if attempt < max_rounds:
            current_prompt = _artifact_followup_prompt(final_result, attempt)
    assistant_text = _collect_assistant_text(agent)
    return json.dumps(
        {
            "run_ids": run_ids,
            "final_artifact_status": final_result.status if final_result else "unknown",
            "artifact_warnings": final_result.warnings if final_result else [],
            "assistant_text": assistant_text,
        },
        ensure_ascii=False,
        indent=2,
    )


def _artifact_followup_prompt(result: DiscoveryResult, attempt: int) -> str:
    warnings = "\n".join(f"- {warning}" for warning in result.warnings) or "- Unknown artifact validation warning."
    error = f"\nError: {result.error}" if result.error else ""
    return f"""The previous CubePi discovery round finished, but the DataElf artifact contract is still incomplete.

Attempt: {attempt}
{error}

Validation warnings:
{warnings}

Do not restart broad exploration. Use the workspace evidence already collected, then write the required outputs now:

1. Call write_candidate_signal for at least one candidate signal.
2. Call write_workspace_file to create one deep-dive report under deep_dives/*.md.
3. Call write_insight_candidate for 1 to 3 insight candidates.
4. Call write_final_brief with a concise final brief.

Each insight must include insight_id, title, thesis, why_now, supporting_signals, analysis_artifacts, related_entities, external_support, counterarguments, confidence, and next_questions. If external search was unavailable or weak, state that explicitly instead of fabricating evidence."""


def _build_bound_model(cubepi: Any, provider: str | None, model: str | None) -> Any:
    provider_name, model_id = _split_model(provider, model)
    if not model_id:
        raise RuntimeError("CubePi model is missing. Set DATAELF_CUBEPI_MODEL or DATAELF_MODEL.")
    if provider_name == "anthropic":
        provider_cls = cubepi.providers.get_anthropic_provider()
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL")
    else:
        provider_cls = cubepi.providers.get_openai_provider()
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
    provider_obj = provider_cls(api_key=api_key, base_url=base_url, provider_id=provider_name)
    return provider_obj.model(model_id)


def _split_model(provider: str | None, model: str | None) -> tuple[str, str | None]:
    provider_name = (provider or "openai").strip().lower()
    model_id = model.strip() if isinstance(model, str) and model.strip() else None
    if model_id and ":" in model_id:
        prefix, rest = model_id.split(":", 1)
        if prefix in {"openai", "anthropic"}:
            provider_name = prefix
            model_id = rest
    return provider_name, model_id


def _collect_assistant_text(agent: Any) -> str:
    messages = getattr(getattr(agent, "state", None), "messages", [])
    chunks: list[str] = []
    for message in messages:
        if getattr(message, "role", "") != "assistant":
            continue
        for content in getattr(message, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _find_agent_class(cubepi: Any) -> Any | None:
    for name in ["Agent", "Pi", "CubePiAgent"]:
        value = getattr(cubepi, name, None)
        if value is not None:
            return value
    agents_mod = getattr(cubepi, "agents", None)
    if agents_mod is not None:
        for name in ["Agent", "Pi", "CubePiAgent"]:
            value = getattr(agents_mod, name, None)
            if value is not None:
                return value
    return None


def _build_tool_functions(cubepi: Any, toolbox: CubePiWorkspaceTools) -> list[Callable[..., Any]]:
    decorator = _find_tool_decorator(cubepi)

    def maybe_tool(fn: Callable[..., Any], *, name: str, description: str) -> Callable[..., Any]:
        if decorator:
            try:
                return decorator(name=name, description=description)(fn)
            except TypeError:
                return decorator(fn)
        return fn

    async def search_papers(
        sub_domains: list[str] | None = None,
        domains: list[str] | None = None,
        keyword: str | None = None,
        sort_type: str = "heat",
        page: int = 1,
        size: int = 50,
    ) -> str:
        """Search AI Index papers and persist raw response plus normalized workspace CSV rows."""
        return await _call_tool(
            toolbox.search_papers,
            sub_domains=sub_domains,
            domains=domains,
            keyword=keyword,
            sort_type=sort_type,
            page=page,
            size=size,
        )

    async def search_institutions(
        sub_domains: list[str] | None = None,
        domains: list[str] | None = None,
        keyword: str | None = None,
        name: str | None = None,
        sort_type: str = "heat",
        page: int = 1,
        size: int = 50,
    ) -> str:
        """Search AI Index institutions and persist raw response plus normalized workspace CSV rows."""
        return await _call_tool(
            toolbox.search_institutions,
            sub_domains=sub_domains,
            domains=domains,
            keyword=keyword,
            name=name,
            sort_type=sort_type,
            page=page,
            size=size,
        )

    async def search_scholars(
        sub_domains: list[str] | None = None,
        domains: list[str] | None = None,
        keyword: str | None = None,
        name: str | None = None,
        sort_type: str = "heat",
        page: int = 1,
        size: int = 50,
    ) -> str:
        """Search AI Index scholars and persist raw response plus normalized workspace CSV rows."""
        return await _call_tool(
            toolbox.search_scholars,
            sub_domains=sub_domains,
            domains=domains,
            keyword=keyword,
            name=name,
            sort_type=sort_type,
            page=page,
            size=size,
        )

    async def fetch_institution_funding(institution_id: str) -> str:
        """Fetch AI Index funding profile for one institution id and persist derived funding tables."""
        return await _call_tool(toolbox.fetch_institution_funding, institution_id=institution_id)

    async def list_workspace_files(relative_dir: str = ".", pattern: str = "*", max_files: int = 200) -> str:
        """List files under the DataElf job workspace."""
        return await _call_tool(toolbox.list_workspace_files, relative_dir=relative_dir, pattern=pattern, max_files=max_files)

    async def read_workspace_file(relative_path: str, max_chars: int = 12000) -> str:
        """Read a workspace file by relative path."""
        return await _call_tool(toolbox.read_workspace_file, relative_path=relative_path, max_chars=max_chars)

    async def write_workspace_file(relative_path: str, content: str, append: bool = False) -> str:
        """Write a file under scripts, notes, deep_dives, insights, raw, tables, or logs."""
        return await _call_tool(toolbox.write_workspace_file, relative_path=relative_path, content=content, append=append)

    async def execute_python(code: str | None = None, script_path: str | None = None, timeout_seconds: int = 120) -> str:
        """Run a Python script in the workspace; provide inline code or an existing workspace script_path."""
        return await _call_tool(toolbox.execute_python, code=code, script_path=script_path, timeout_seconds=timeout_seconds)

    async def web_search(query: str, max_results: int = 5) -> str:
        """Search the external web through the configured Tavily key and save observations in the workspace."""
        return await _call_tool(toolbox.web_search, query=query, max_results=max_results)

    async def fetch_url(url: str, max_chars: int = 5000) -> str:
        """Fetch one external URL and save readable text under raw/web."""
        return await _call_tool(toolbox.fetch_url, url=url, max_chars=max_chars)

    async def write_candidate_signal(signal: dict[str, Any]) -> str:
        """Append or update one item in insights/candidate_signals.json."""
        return await _call_tool(toolbox.write_candidate_signal, signal=signal)

    async def write_insight_candidate(insight: dict[str, Any]) -> str:
        """Append or update one item in insights/insight_candidates.json."""
        return await _call_tool(toolbox.write_insight_candidate, insight=insight)

    async def write_final_brief(markdown: str) -> str:
        """Write insights/final_brief.md."""
        return await _call_tool(toolbox.write_final_brief, markdown=markdown)

    return [
        maybe_tool(search_papers, name="search_papers", description=search_papers.__doc__ or ""),
        maybe_tool(search_institutions, name="search_institutions", description=search_institutions.__doc__ or ""),
        maybe_tool(search_scholars, name="search_scholars", description=search_scholars.__doc__ or ""),
        maybe_tool(fetch_institution_funding, name="fetch_institution_funding", description=fetch_institution_funding.__doc__ or ""),
        maybe_tool(list_workspace_files, name="list_workspace_files", description=list_workspace_files.__doc__ or ""),
        maybe_tool(read_workspace_file, name="read_workspace_file", description=read_workspace_file.__doc__ or ""),
        maybe_tool(write_workspace_file, name="write_workspace_file", description=write_workspace_file.__doc__ or ""),
        maybe_tool(execute_python, name="execute_python", description=execute_python.__doc__ or ""),
        maybe_tool(web_search, name="web_search", description=web_search.__doc__ or ""),
        maybe_tool(fetch_url, name="fetch_url", description=fetch_url.__doc__ or ""),
        maybe_tool(write_candidate_signal, name="write_candidate_signal", description=write_candidate_signal.__doc__ or ""),
        maybe_tool(write_insight_candidate, name="write_insight_candidate", description=write_insight_candidate.__doc__ or ""),
        maybe_tool(write_final_brief, name="write_final_brief", description=write_final_brief.__doc__ or ""),
    ]


async def _call_tool(fn: Callable[..., Any], **kwargs: Any) -> str:
    clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
    result = await asyncio.to_thread(fn, **clean_kwargs)
    return json.dumps(result, ensure_ascii=False, default=str)


def _find_tool_decorator(cubepi: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]] | None:
    direct = getattr(cubepi, "tool", None)
    if callable(direct):
        return direct
    tools_mod = getattr(cubepi, "tools", None)
    if tools_mod is not None:
        value = getattr(tools_mod, "tool", None)
        if callable(value):
            return value
    return None


def _write_dry_run_artifacts(job: DiscoveryJob, workspace_path: Path, tools: CubePiWorkspaceTools) -> None:
    tools.write_candidate_signal(
        {
            "signal_id": "sig_cubepi_dry_run_001",
            "signal_type": "cross_domain_connection",
            "summary": "CubePi dry-run verified the DataElf workspace and artifact contract.",
            "why_might_matter": "This confirms the experimental CubePi backend can participate in the same DiscoveryWorkflow contract.",
            "supporting_tables": ["papers.csv", "institutions.csv"],
            "related_entities": ["Paper", "Institution", "WebSource"],
            "suggested_deep_dive": ["Replace dry-run with real CubePi execution and compare tool-use behavior against dcode."],
            "initial_score": {"novelty": 0.1, "magnitude": 0.1, "strategic_relevance": 0.3},
            "status": "needs_real_run",
        }
    )
    tools.write_insight_candidate(
        {
            "insight_id": "ins_cubepi_dry_run_001",
            "title": "CubePi backend is wired into the DataElf discovery contract",
            "thesis": "The dry-run path validates backend selection, workspace access, artifact writing, and quality review without making a real model call.",
            "why_now": "DataElf needs a parallel Option 2 backend for comparison against the DeepAgentsCode runner.",
            "supporting_signals": ["sig_cubepi_dry_run_001"],
            "analysis_artifacts": ["scripts/cubepi_dry_run.py", "deep_dives/cubepi_dry_run.md"],
            "related_entities": ["Backend:CubePi", "Backend:DeepAgentsCode", "Workspace:DataElf"],
            "external_support": [{"source_id": "dry_run", "summary": "No external facts used in dry-run mode."}],
            "counterarguments": ["Dry-run mode does not evaluate CubePi's real exploration quality."],
            "confidence": 0.5,
            "next_questions": ["Install cubepi and run a real comparison job with provider credentials."],
        }
    )
    tools.write_workspace_file("scripts/cubepi_dry_run.py", 'print("cubepi dry run")\n')
    tools.write_workspace_file("deep_dives/cubepi_dry_run.md", "# CubePi Dry Run\n\nDry-run artifact for DataElf backend comparison.\n")
    tools.write_workspace_file(
        "tables/external_findings.csv",
        "finding_id,source_id,finding_type,summary,supports,challenges,confidence,url,source_raw\n"
        "cubepi_dry_run,dry_run,dry_run,No external facts used in dry-run mode,ins_cubepi_dry_run_001,,0.0,,\n",
    )
    tools.write_final_brief(f"# CubePi Dry Run Brief\n\nJob `{job.job_id}` completed in CubePi dry-run mode.\n")
    (workspace_path / "logs" / "cubepi_stdout.log").write_text("CubePi dry-run completed.\n", encoding="utf-8")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
