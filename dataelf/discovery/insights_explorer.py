from __future__ import annotations

from dataelf.discovery.base import DiscoveryContext, DiscoveryResult, InsightsExplorer
from dataelf.discovery.deepagents_code_cli_explorer import DeepAgentsCodeCliInsightsExplorer


# Backward-compatible import surface for existing code/tests.
DeepAgentsCodeInsightsExplorer = DeepAgentsCodeCliInsightsExplorer

__all__ = [
    "DiscoveryContext",
    "DiscoveryResult",
    "InsightsExplorer",
    "DeepAgentsCodeCliInsightsExplorer",
    "DeepAgentsCodeInsightsExplorer",
]
