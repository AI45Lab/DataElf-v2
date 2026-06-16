from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from dataelf.discovery.base import DiscoveryContext, DiscoveryResult
from dataelf.discovery.prompt_builder import write_discovery_prompt
from dataelf.discovery.result_parser import parse_discovery_result
from dataelf.schemas import DiscoveryJob


DEFAULT_DCODE_BINARY = "dcode"
DEFAULT_SHELL_ALLOW_LIST = "all"
DEFAULT_DCODE_EXTRA_ARGS = ""
SUBAGENTS = {
    "breadth-scout": (
        "Scan AI Index tables and raw files to generate many candidate signals for technology intelligence discovery.",
        "You are the Breadth Scout for DataElf. Your job is to scan broadly and generate candidate signals. Do not produce final insights.",
    ),
    "code-analyst": (
        "Write Python scripts to analyze AI Index tables, compute aggregations, detect anomalies, and generate quantitative artifacts.",
        "You are the Code Analyst for DataElf. Your job is to write and run Python scripts under scripts/ and save outputs under tables/ and deep_dives/.",
    ),
    "web-investigator": (
        "Use web_search and fetch_url to investigate external signals that explain or challenge candidate insights.",
        "You are the Web Investigator for DataElf. Your job is to use external web signals to support or challenge candidate signals.",
    ),
    "skeptic": (
        "Challenge candidate insights by finding low-base effects, weak evidence, obviousness, missing support, and alternative explanations.",
        "You are the Skeptic for DataElf. Your job is to challenge candidate insights. Do not generate new insights.",
    ),
    "insight-synthesizer": (
        "Merge candidate signals, quantitative analysis, web findings, and skeptic review into final structured insight candidates.",
        "You are the Insight Synthesizer for DataElf. Your job is to produce final insight_candidates.json and final_brief.md.",
    ),
}


class DeepAgentsCodeCliInsightsExplorer:
    """Discovery Lab runner that delegates insights_explore to DeepAgentsCode CLI.

    This is intentionally a CLI runner for M1 validation. It is not the final
    DataElf-native agent runtime integration. The stable contract is the
    workspace artifacts, especially `insights/insight_candidates.json`.
    """

    def __init__(
        self,
        dcode_binary: str | None = None,
        shell_allow_list: str | None = None,
        auto_approve: bool = True,
        extra_args: str | None = None,
    ):
        self.dcode_binary = dcode_binary or os.getenv("DATAELF_DCODE_BINARY", DEFAULT_DCODE_BINARY)
        self.shell_allow_list = shell_allow_list or os.getenv("DATAELF_DCODE_SHELL_ALLOW_LIST", DEFAULT_SHELL_ALLOW_LIST)
        self.auto_approve = auto_approve
        self.extra_args = extra_args if extra_args is not None else os.getenv("DATAELF_DCODE_EXTRA_ARGS", DEFAULT_DCODE_EXTRA_ARGS)

    def run(self, job: DiscoveryJob, context: DiscoveryContext) -> DiscoveryResult:
        workspace_path = Path(context.workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)
        logs_dir = workspace_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / "dcode_stdout.log"
        stderr_path = logs_dir / "dcode_stderr.log"

        prompt_path = write_discovery_prompt(job, context)
        self._init_project_agents(workspace_path)
        command = self._build_command(prompt_path.read_text(encoding="utf-8"), context.model)
        env = self._build_env(workspace_path, context)
        timeout = _timeout_seconds(job)

        try:
            completed = subprocess.run(
                command,
                cwd=workspace_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            message = "DeepAgentsCode CLI not found. Please install deepagents-code and ensure dcode is on PATH, or set DATAELF_DCODE_BINARY."
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(message + "\n", encoding="utf-8")
            return DiscoveryResult(job_id=job.job_id, status="failed", workspace_path=str(workspace_path), warnings=[message], error=message)
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text((exc.stderr or "") + f"\nDeepAgentsCode CLI timed out after {timeout} seconds.\n", encoding="utf-8")
            result = parse_discovery_result(workspace_path, job_id=job.job_id)
            result.status = "incomplete" if result.status == "completed" else result.status
            result.warnings.append(f"DeepAgentsCode CLI timed out after {timeout} seconds.")
            if result.error is None:
                result.error = "dcode_timeout"
            return result

        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        result = parse_discovery_result(workspace_path, job_id=job.job_id)
        if completed.returncode != 0:
            result.warnings.append(f"DeepAgentsCode CLI exited with code {completed.returncode}. See logs/dcode_stderr.log.")
            if result.status != "completed" and result.error is None:
                result.error = f"dcode_exit_{completed.returncode}"
        return result

    def _build_command(self, prompt: str, model: str | None) -> list[str]:
        command = [self.dcode_binary]
        if self.auto_approve:
            command.append("--auto-approve")
        if self.shell_allow_list:
            command.extend(["-S", self.shell_allow_list])
        if model:
            command.extend(["--model", model])
        if self.extra_args:
            command.extend(shlex.split(self.extra_args))
        command.extend(["-n", prompt])
        return command

    def _build_env(self, workspace_path: Path, context: DiscoveryContext) -> dict[str, str]:
        env = os.environ.copy()
        env.update({key: str(value) for key, value in context.env.items()})
        repo_root = Path(__file__).resolve().parents[2]
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(repo_root) if not existing_pythonpath else f"{repo_root}{os.pathsep}{existing_pythonpath}"
        env["DATAELF_WORKSPACE"] = str(workspace_path)
        env["DATAELF_JOB_WORKSPACE"] = str(workspace_path)
        env["DATAELF_DOMAIN"] = context.domain
        if context.model:
            env["DATAELF_MODEL"] = context.model
        return env

    def _init_project_agents(self, workspace_path: Path) -> None:
        agents_root = workspace_path / ".deepagents" / "agents"
        agents_root.mkdir(parents=True, exist_ok=True)
        for name, (description, body) in SUBAGENTS.items():
            agent_dir = agents_root / name
            agent_dir.mkdir(parents=True, exist_ok=True)
            path = agent_dir / "AGENTS.md"
            if path.exists():
                continue
            path.write_text(
                "\n".join(
                    [
                        "---",
                        f"name: {name}",
                        f"description: {description}",
                        "---",
                        "",
                        body,
                        "",
                    ]
                ),
                encoding="utf-8",
            )


def _timeout_seconds(job: DiscoveryJob) -> int:
    minutes = job.constraints.get("max_runtime_minutes", 30)
    try:
        return max(60, int(float(minutes) * 60))
    except (TypeError, ValueError):
        return 1800
