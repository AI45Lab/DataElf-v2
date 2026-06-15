from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


def update_tables_from_response(workspace_path: Path, response: dict[str, Any]) -> dict[str, int]:
    endpoint = response.get("endpoint", "")
    if "paper/search" in endpoint:
        tables = normalize_papers_response(response)
    elif "institutions/search" in endpoint:
        tables = normalize_institutions_response(response)
    elif "scholar/search" in endpoint:
        tables = normalize_scholars_response(response)
    elif "funding-profile" in endpoint:
        institution_id = str(response.get("request", {}).get("institution_id", ""))
        tables = normalize_funding_response(response, institution_id)
    else:
        tables = {}
    write_tables(workspace_path, tables, append=True)
    return {name: len(rows) for name, rows in tables.items()}


def normalize_papers_response(response: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = _items(response)
    papers: list[dict[str, Any]] = []
    paper_author: list[dict[str, Any]] = []
    paper_institution: list[dict[str, Any]] = []
    for item in rows:
        paper_id = _id(item, "paper")
        institution_ids = _list(item.get("institution_ids")) or _list(item.get("institution_id"))
        author_objs = item.get("authors") if isinstance(item.get("authors"), list) else []
        author_ids = _list(item.get("author_ids"))
        papers.append(
            {
                "paper_id": paper_id,
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "pub_date": item.get("pub_date") or item.get("published_at") or "",
                "venue": item.get("conference_abbreviation") or item.get("conference_name") or item.get("journal_abbreviation") or item.get("venue") or "",
                "citation_count": item.get("cited_by_count") or item.get("citation_count") or 0,
                "heat": _heat(item),
                "previous_heat": _previous_heat(item),
                "domains": _jsonish(item.get("domains") or item.get("fields") or []),
                "sub_domains": _jsonish(item.get("sub_domains") or []),
                "institution_ids": _jsonish(institution_ids),
                "source_raw": response.get("raw_uri", ""),
            }
        )
        for idx, author in enumerate(author_objs):
            paper_author.append(
                {
                    "paper_id": paper_id,
                    "scholar_id": author.get("author_id", ""),
                    "display_name": author.get("display_name", ""),
                    "is_first_author": bool(author.get("is_first_author")),
                    "is_corresponding_author": bool(author.get("is_corresponding_author")),
                    "author_order": idx + 1,
                }
            )
        for idx, author_id in enumerate(author_ids):
            paper_author.append(
                {
                    "paper_id": paper_id,
                    "scholar_id": author_id,
                    "display_name": "",
                    "is_first_author": idx == 0,
                    "is_corresponding_author": False,
                    "author_order": idx + 1,
                }
            )
        for institution_id in institution_ids:
            paper_institution.append({"paper_id": paper_id, "institution_id": institution_id})
    return {"papers": papers, "paper_author": paper_author, "paper_institution": paper_institution}


def normalize_institutions_response(response: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = []
    for item in _items(response):
        radar = item.get("index_radar_display") or {}
        rows.append(
            {
                "institution_id": _id(item, "institution"),
                "name": item.get("name", ""),
                "country_code": item.get("country_code") or item.get("country") or "",
                "paper_count": item.get("paper_count", 0),
                "scholar_count": item.get("author_count") or item.get("scholar_count") or 0,
                "heat": _heat(item),
                "previous_heat": _previous_heat(item),
                "funding_total_usd": item.get("funding_total_usd", ""),
                "domains": _jsonish(item.get("domains") or item.get("fields") or []),
                "sub_tags": _jsonish(item.get("sub_tags") or []),
                "academic_impact": radar.get("academic_impact", ""),
                "capital_signal": radar.get("capital_signal", ""),
                "innovation_power": radar.get("innovation_power", ""),
                "media_momentum": radar.get("media_momentum", ""),
                "talent_momentum": radar.get("talent_momentum", ""),
                "total_score": radar.get("total_score", ""),
                "source_raw": response.get("raw_uri", ""),
            }
        )
    return {"institutions": rows}


def normalize_scholars_response(response: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    scholars: list[dict[str, Any]] = []
    scholar_institution: list[dict[str, Any]] = []
    for item in _items(response):
        scholar_id = _id(item, "scholar")
        institution_ids = _list(item.get("institution_ids")) or _list(item.get("institution_id"))
        scholars.append(
            {
                "scholar_id": scholar_id,
                "display_name": item.get("display_name") or item.get("name") or "",
                "institution": item.get("institution", ""),
                "institution_ids": _jsonish(institution_ids),
                "paper_count": item.get("paper_count") or len(_list(item.get("paper_ids"))),
                "cited_by_count": item.get("cited_by_count", ""),
                "heat": _heat(item),
                "previous_heat": _previous_heat(item),
                "domains": _jsonish(item.get("domains") or item.get("fields") or []),
                "sub_domains": _jsonish(item.get("sub_domains") or []),
                "country_code": item.get("country_code", ""),
                "source_raw": response.get("raw_uri", ""),
            }
        )
        for institution_id in institution_ids:
            scholar_institution.append({"scholar_id": scholar_id, "institution_id": institution_id})
    return {"scholars": scholars, "scholar_institution": scholar_institution}


def normalize_funding_response(response: dict[str, Any], institution_id: str) -> dict[str, list[dict[str, Any]]]:
    data = response.get("data", {})
    rows: list[dict[str, Any]] = []
    rounds = ((data.get("funding") or {}).get("funding_rounds") or []) if isinstance(data, dict) else []
    for idx, item in enumerate(rounds):
        money = item.get("money_raised") or {}
        rows.append(
            {
                "funding_id": item.get("id") or f"{institution_id}_funding_{idx + 1}",
                "institution_id": institution_id,
                "title": item.get("title", ""),
                "announced_on": item.get("announced_on", ""),
                "currency": money.get("currency", ""),
                "value": money.get("value", ""),
                "value_usd": money.get("value_usd", ""),
                "lead_investors": _jsonish(item.get("lead_investors") or []),
                "source_raw": response.get("raw_uri", ""),
            }
        )
    if not rows:
        summary = data.get("summary", {}) if isinstance(data, dict) else {}
        total = summary.get("total_funding", {}) if isinstance(summary, dict) else {}
        rows.append(
            {
                "funding_id": f"{institution_id}_funding_summary",
                "institution_id": institution_id,
                "title": "Funding summary",
                "announced_on": "",
                "currency": total.get("currency", ""),
                "value": total.get("value", ""),
                "value_usd": total.get("value_usd", ""),
                "lead_investors": "[]",
                "source_raw": response.get("raw_uri", ""),
            }
        )
    return {"funding": rows}


def write_tables(workspace_path: Path, tables: dict[str, list[dict[str, Any]]], append: bool = True) -> None:
    tables_dir = workspace_path / "domains" / "ai_index" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        path = tables_dir / f"{name}.csv"
        merged = _read_csv(path) if append and path.exists() else []
        merged.extend(rows)
        unique = _dedupe(merged)
        _write_csv(path, unique)


def read_table(workspace_path: Path, name: str) -> list[dict[str, str]]:
    return _read_csv(workspace_path / "domains" / "ai_index" / "tables" / f"{name}.csv")


def _items(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return data["list"]
    if isinstance(data, list):
        return data
    return []


def _id(item: dict[str, Any], kind: str) -> str:
    return str(item.get(f"{kind}_id") or item.get("id") or "")


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return [str(value)]


def _heat(item: dict[str, Any]) -> Any:
    heat = item.get("heat")
    if isinstance(heat, dict):
        return heat.get("half_year") or heat.get("month") or ""
    return heat if heat is not None else ""


def _previous_heat(item: dict[str, Any]) -> Any:
    heat = item.get("heat")
    if isinstance(heat, dict):
        return heat.get("previous_half_year", "")
    return ""


def _jsonish(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        if not path.exists():
            path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique

