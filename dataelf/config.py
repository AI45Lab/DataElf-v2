from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class DataElfConfig(BaseModel):
    workspace_dir: Path = Field(default_factory=lambda: Path(".dataelf"))
    sqlite_path: Path = Field(default_factory=lambda: Path(".dataelf/dataelf.sqlite"))
    raw_dir: Path = Field(default_factory=lambda: Path(".dataelf/raw"))
    fixtures_dir: Path = Field(default_factory=lambda: Path("fixtures/ai_index"))
    skills_dir: Path = Field(default_factory=lambda: Path("skills"))
    model: str = "openai:gpt-5.4"

    @classmethod
    def from_env(cls) -> "DataElfConfig":
        workspace = Path(os.getenv("DATAELF_WORKSPACE", ".dataelf"))
        return cls(
            workspace_dir=workspace,
            sqlite_path=workspace / "dataelf.sqlite",
            raw_dir=workspace / "raw",
            fixtures_dir=Path(os.getenv("DATAELF_FIXTURES_DIR", "fixtures/ai_index")),
            skills_dir=Path(os.getenv("DATAELF_SKILLS_DIR", "skills")),
            model=os.getenv("DATAELF_MODEL", "openai:gpt-5.4"),
        )

    def ensure_dirs(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)


def apply_llm_env_aliases() -> None:
    if os.getenv("DATAELF_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["DATAELF_API_KEY"]
    if os.getenv("DATAELF_BASE_URL") and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = os.environ["DATAELF_BASE_URL"]


def validate_model_env(model: str) -> None:
    if model.startswith("ollama:"):
        return
    if model.startswith("openai:") and not os.getenv("OPENAI_API_KEY") and not os.getenv("DATAELF_API_KEY"):
        raise RuntimeError(
            "DeepAgentsAdapter requires a tool-calling model.\n"
            "Set DATAELF_MODEL, for example:\n"
            '  export DATAELF_MODEL="openai:gpt-5.4"\n'
            '  export OPENAI_API_KEY="..."\n'
            "For an OpenAI-compatible endpoint, also set OPENAI_BASE_URL or DATAELF_BASE_URL.\n"
            "Or use another Deep Agents supported provider, such as google_genai, "
            "anthropic, openrouter, fireworks, baseten, or ollama."
        )
