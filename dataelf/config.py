from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_AI_INDEX_BASE_URL = "https://index.shlab.org.cn/api/v2"
DEFAULT_AI_INDEX_API_KEY = "ak_0XWHy2OQpSKnaKHL"
DEFAULT_AI_INDEX_MODE = "api"
DEFAULT_ENABLE_SQLITE = False
DEFAULT_INSIGHTS_EXPLORER = "deepagentscode"


class DataElfConfig(BaseModel):
    workspace_dir: Path = Field(default_factory=lambda: Path(".dataelf"))
    sqlite_path: Path = Field(default_factory=lambda: Path(".dataelf/dataelf.sqlite"))
    raw_dir: Path = Field(default_factory=lambda: Path(".dataelf/raw"))
    workspaces_dir: Path = Field(default_factory=lambda: Path(".dataelf/workspaces"))
    fixtures_dir: Path = Field(default_factory=lambda: Path("fixtures/ai_index"))
    model: str | None = None
    ai_index_mode: str = DEFAULT_AI_INDEX_MODE
    ai_index_base_url: str = DEFAULT_AI_INDEX_BASE_URL
    ai_index_api_key: str = DEFAULT_AI_INDEX_API_KEY
    enable_sqlite: bool = DEFAULT_ENABLE_SQLITE
    insights_explorer: str = DEFAULT_INSIGHTS_EXPLORER
    cubepi_provider: str | None = None
    cubepi_model: str | None = None
    cubepi_dry_run: bool = False

    @classmethod
    def from_env(cls) -> "DataElfConfig":
        workspace = Path(os.getenv("DATAELF_WORKSPACE", ".dataelf"))
        return cls(
            workspace_dir=workspace,
            sqlite_path=workspace / "dataelf.sqlite",
            raw_dir=workspace / "raw",
            workspaces_dir=workspace / "workspaces",
            fixtures_dir=Path(os.getenv("DATAELF_FIXTURES_DIR", "fixtures/ai_index")),
            model=os.getenv("DATAELF_MODEL"),
            ai_index_mode=os.getenv("DATAELF_AI_INDEX_MODE", DEFAULT_AI_INDEX_MODE),
            ai_index_base_url=os.getenv("AI_INDEX_BASE_URL", DEFAULT_AI_INDEX_BASE_URL),
            ai_index_api_key=os.getenv("AI_INDEX_API_KEY", DEFAULT_AI_INDEX_API_KEY),
            enable_sqlite=_env_bool("DATAELF_ENABLE_SQLITE", DEFAULT_ENABLE_SQLITE),
            insights_explorer=os.getenv("DATAELF_INSIGHTS_EXPLORER", DEFAULT_INSIGHTS_EXPLORER),
            cubepi_provider=os.getenv("DATAELF_CUBEPI_PROVIDER"),
            cubepi_model=os.getenv("DATAELF_CUBEPI_MODEL"),
            cubepi_dry_run=_env_bool("DATAELF_CUBEPI_DRY_RUN", False),
        )

    def ensure_dirs(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
