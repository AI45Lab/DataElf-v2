from __future__ import annotations

from dataelf.discovery.base import DiscoveryContext, DiscoveryResult, InsightsExplorer
from dataelf.config import DataElfConfig
from dataelf.discovery.deepagents_code_cli_explorer import DeepAgentsCodeCliInsightsExplorer


# Backward-compatible import surface for existing code/tests.
DeepAgentsCodeInsightsExplorer = DeepAgentsCodeCliInsightsExplorer


def create_insights_explorer(config: DataElfConfig) -> InsightsExplorer:
    explorer_name = (config.insights_explorer or "deepagentscode").strip().lower()
    if explorer_name in {"deepagentscode", "deepagents_code", "dcode", "deepagents"}:
        return DeepAgentsCodeCliInsightsExplorer()
    if explorer_name in {"cubepi", "cube_pi", "pi"}:
        from dataelf.discovery.cubepi_insights_explorer import CubePiInsightsExplorer

        return CubePiInsightsExplorer()
    raise ValueError(f"Unknown DATAELF_INSIGHTS_EXPLORER={config.insights_explorer!r}. Expected deepagentscode or cubepi.")

__all__ = [
    "DiscoveryContext",
    "DiscoveryResult",
    "InsightsExplorer",
    "DeepAgentsCodeCliInsightsExplorer",
    "DeepAgentsCodeInsightsExplorer",
    "create_insights_explorer",
]
