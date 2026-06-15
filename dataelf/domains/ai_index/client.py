from __future__ import annotations

from pathlib import Path
from typing import Any

from dataelf.config import DataElfConfig
from dataelf.domains.ai_index.connector import AIIndexConnector
from dataelf.domains.ai_index.table_builder import _items, normalize_institutions_response, normalize_papers_response, normalize_scholars_response, update_tables_from_response, write_tables


class AIIndexClient:
    def __init__(self, connector: AIIndexConnector, workspace_path: Path | None = None):
        self.connector = connector
        self.workspace_path = workspace_path

    @classmethod
    def from_env(cls, workspace_path: str | Path | None = None) -> "AIIndexClient":
        config = DataElfConfig.from_env()
        path = Path(workspace_path) if workspace_path else None
        connector = AIIndexConnector(
            mode=config.ai_index_mode,
            base_url=config.ai_index_base_url,
            api_key=config.ai_index_api_key,
            fixtures_dir=config.fixtures_dir,
            workspace_path=path,
        )
        return cls(connector=connector, workspace_path=path)

    def search_papers(self, **kwargs: Any) -> dict[str, Any]:
        response = self.connector.search_papers(**kwargs)
        self._update_tables(response)
        return response

    def search_institutions(self, **kwargs: Any) -> dict[str, Any]:
        response = self.connector.search_institutions(**kwargs)
        self._update_tables(response)
        return response

    def search_scholars(self, **kwargs: Any) -> dict[str, Any]:
        response = self.connector.search_scholars(**kwargs)
        self._update_tables(response)
        return response

    def fetch_institution_funding(self, institution_id: str) -> dict[str, Any]:
        response = self.connector.fetch_institution_funding(institution_id)
        self._update_tables(response)
        return response

    def collect_papers(self, max_pages: int = 3, size: int = 50, **kwargs: Any):
        return self._collect("papers", max_pages=max_pages, size=size, **kwargs)

    def collect_institutions(self, max_pages: int = 3, size: int = 50, **kwargs: Any):
        return self._collect("institutions", max_pages=max_pages, size=size, **kwargs)

    def collect_scholars(self, max_pages: int = 3, size: int = 50, **kwargs: Any):
        return self._collect("scholars", max_pages=max_pages, size=size, **kwargs)

    def to_dataframe(self, table_name: str, response: dict[str, Any]):
        rows = self.to_rows(table_name, response)
        try:
            import pandas as pd
        except ImportError:
            return rows
        return pd.DataFrame(rows)

    def to_rows(self, table_name: str, response: dict[str, Any]) -> list[dict[str, Any]]:
        if table_name == "papers":
            return normalize_papers_response(response).get("papers", [])
        if table_name == "institutions":
            return normalize_institutions_response(response).get("institutions", [])
        if table_name == "scholars":
            return normalize_scholars_response(response).get("scholars", [])
        return _items(response)

    def save_table(self, table_name: str, data: Any) -> None:
        if self.workspace_path is None:
            raise ValueError("AIIndexClient.save_table requires workspace_path.")
        rows = _rows_from_data(data)
        write_tables(self.workspace_path, {table_name: rows}, append=True)

    def _collect(self, kind: str, max_pages: int, size: int, **kwargs: Any):
        all_rows: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            response = getattr(self, f"search_{kind}")(**kwargs, page=page, size=size)
            rows = _items(response)
            all_rows.extend(rows)
            total = response.get("data", {}).get("total") if isinstance(response.get("data"), dict) else None
            if not rows or (total is not None and len(all_rows) >= int(total)):
                break
        try:
            import pandas as pd
        except ImportError:
            return all_rows
        return pd.DataFrame(all_rows)

    def _update_tables(self, response: dict[str, Any]) -> None:
        if self.workspace_path is not None:
            update_tables_from_response(self.workspace_path, response)


def _rows_from_data(data: Any) -> list[dict[str, Any]]:
    if hasattr(data, "to_dict"):
        return data.to_dict(orient="records")
    if isinstance(data, list):
        return [dict(row) for row in data]
    raise TypeError("save_table expects a pandas DataFrame or list[dict].")

