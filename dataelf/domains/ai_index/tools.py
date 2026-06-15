from __future__ import annotations

import os
from typing import Any

from dataelf.domains.ai_index.client import AIIndexClient


class AIIndexDiscoveryTools:
    def __init__(self, client: AIIndexClient):
        self.client = client

    def search_papers(self, **kwargs: Any) -> dict[str, Any]:
        return _compact(self.client.search_papers(**kwargs))

    def search_institutions(self, **kwargs: Any) -> dict[str, Any]:
        return _compact(self.client.search_institutions(**kwargs))

    def search_scholars(self, **kwargs: Any) -> dict[str, Any]:
        return _compact(self.client.search_scholars(**kwargs))

    def fetch_institution_funding(self, institution_id: str) -> dict[str, Any]:
        return _compact(self.client.fetch_institution_funding(institution_id))

    def web_search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        provider = os.getenv("WEB_SEARCH_PROVIDER") or os.getenv("TAVILY_API_KEY")
        if not provider:
            return {
                "configured": False,
                "query": query,
                "results": [],
                "error": "web_search is not configured. Set WEB_SEARCH_PROVIDER/TAVILY_API_KEY before relying on external web facts.",
            }
        return {
            "configured": False,
            "query": query,
            "results": [],
            "error": "web_search provider wiring is reserved for the Insight Explorer owner in M2.",
        }

    def fetch_url(self, url: str) -> dict[str, Any]:
        return {
            "configured": False,
            "url": url,
            "text": "",
            "error": "fetch_url is intentionally a stub in M1; do not fabricate web facts.",
        }


def _compact(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        previews = data["list"][:10]
        total = data.get("total", len(previews))
    else:
        previews = data
        total = None
    return {
        "source": response.get("source"),
        "mode": response.get("mode"),
        "endpoint": response.get("endpoint"),
        "request": response.get("request", {}),
        "trace_id": response.get("trace_id"),
        "raw_uri": response.get("raw_uri"),
        "total": total,
        "preview": previews,
    }

