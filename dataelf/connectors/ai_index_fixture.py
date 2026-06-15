from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FixtureAIIndexConnector:
    name = "ai_index_fixture"

    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir
        self.institutions = self._load("institutions.json")
        self.papers = self._load("papers.json")
        self.scholars = self._load("scholars.json")

    def _load(self, filename: str) -> list[dict[str, Any]]:
        path = self.fixtures_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Fixture file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def validate(self) -> dict[str, int]:
        return {
            "institutions": len(self.institutions),
            "papers": len(self.papers),
            "scholars": len(self.scholars),
        }

    def search_institutions(self, field: str | None = None, time_window: str = "half_year") -> dict[str, Any]:
        data = self._filter_by_field(self.institutions, field)
        return self._response("search_institutions", {"field": field, "time_window": time_window}, data)

    def search_papers(self, field: str | None = None, time_window: str = "half_year") -> dict[str, Any]:
        data = self._filter_by_field(self.papers, field)
        return self._response("search_papers", {"field": field, "time_window": time_window}, data)

    def search_scholars(self, field: str | None = None, time_window: str = "half_year") -> dict[str, Any]:
        data = self._filter_by_field(self.scholars, field)
        return self._response("search_scholars", {"field": field, "time_window": time_window}, data)

    def fetch_institution(self, institution_id: str) -> dict[str, Any]:
        item = self._find(self.institutions, institution_id, "institution")
        return self._response("fetch_institution", {"institution_id": institution_id}, [item])

    def fetch_paper(self, paper_id: str) -> dict[str, Any]:
        item = self._find(self.papers, paper_id, "paper")
        return self._response("fetch_paper", {"paper_id": paper_id}, [item])

    def fetch_scholar(self, scholar_id: str) -> dict[str, Any]:
        item = self._find(self.scholars, scholar_id, "scholar")
        return self._response("fetch_scholar", {"scholar_id": scholar_id}, [item])

    def _filter_by_field(self, items: list[dict[str, Any]], field: str | None) -> list[dict[str, Any]]:
        if not field:
            return items
        needle = field.casefold()
        return [item for item in items if any(str(value).casefold() == needle for value in item.get("fields", []))]

    def _find(self, items: list[dict[str, Any]], item_id: str, label: str) -> dict[str, Any]:
        for item in items:
            if item.get("id") == item_id:
                return item
        raise KeyError(f"Unknown {label} id: {item_id}")

    def _response(self, endpoint: str, request: dict[str, Any], data: list[dict[str, Any]]) -> dict[str, Any]:
        return {"source": self.name, "endpoint": endpoint, "request": request, "data": data}
