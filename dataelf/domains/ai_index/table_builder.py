from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


TABLE_SCHEMAS: dict[str, list[str]] = {
    "papers": [
        "paper_id",
        "title",
        "abstract",
        "first_authors",
        "corresponding_authors",
        "institution",
        "institution_id",
        "institution_ids",
        "institutions",
        "country_code",
        "pub_date",
        "venue",
        "journal_name",
        "journal_abbreviation",
        "conference_name",
        "conference_abbreviation",
        "conf_award_info",
        "heat",
        "previous_heat",
        "cited_by_count",
        "citation_count",
        "domains",
        "sub_domains",
        "landing_page_url",
        "pdf_url",
        "count_by_year",
        "source_raw",
    ],
    "paper_author": ["paper_id", "scholar_id", "display_name", "is_first_author", "is_corresponding_author", "author_order", "source_raw"],
    "paper_institution": ["paper_id", "institution_id", "institution_name", "is_primary", "source_raw"],
    "paper_yearly_counts": ["paper_id", "year", "cited_by_count", "source_raw"],
    "paper_awards": ["paper_id", "conf", "year", "award_key", "award_title", "source_raw"],
    "institutions": [
        "institution_id",
        "name",
        "image",
        "full_description",
        "country_code",
        "paper_count",
        "author_count",
        "scholar_count",
        "num_employees",
        "heat",
        "previous_heat",
        "funding_total_usd",
        "domains",
        "sub_tags",
        "conference_names",
        "journal_names",
        "award_list",
        "academic_impact",
        "capital_signal",
        "innovation_power",
        "media_momentum",
        "talent_momentum",
        "total_score",
        "source_raw",
    ],
    "institution_awards": ["institution_id", "conf", "year", "award_key", "award_title", "source_raw"],
    "institution_venues": ["institution_id", "venue_type", "venue_name", "source_raw"],
    "scholars": [
        "scholar_id",
        "display_name",
        "avatar",
        "institution",
        "institution_id",
        "institution_ids",
        "institutions",
        "cited_by_count",
        "count_by_year",
        "paper_count",
        "first_author_paper_count",
        "corresponding_paper_count",
        "homepage",
        "is_ethnic_chinese",
        "heat",
        "previous_heat",
        "domains",
        "sub_domains",
        "country_code",
        "journal_names",
        "journal_abbreviations",
        "conference_names",
        "conference_abbreviations",
        "award_list",
        "email",
        "source_raw",
    ],
    "scholar_institution": ["scholar_id", "institution_id", "institution_name", "is_primary", "source_raw"],
    "scholar_yearly_counts": ["scholar_id", "year", "cited_by_count", "source_raw"],
    "scholar_awards": ["scholar_id", "conf", "year", "award_key", "award_title", "source_raw"],
    "scholar_venues": ["scholar_id", "venue_type", "venue_name", "source_raw"],
    "funding": ["funding_id", "institution_id", "uuid", "title", "announced_on", "image_id", "currency", "value", "value_usd", "lead_investors", "source_raw"],
    "funding_summary": [
        "institution_id",
        "total_funding_currency",
        "total_funding_value",
        "total_funding_value_usd",
        "funding_round_count",
        "investor_count",
        "lead_investor_count",
        "invested_round_count",
        "lead_invested_round_count",
        "investment_count",
        "lead_investment_count",
        "source_raw",
    ],
    "funding_rounds": ["funding_id", "institution_id", "uuid", "title", "announced_on", "image_id", "currency", "value", "value_usd", "lead_investors", "source_raw"],
    "funding_investors": [
        "institution_id",
        "investor_record_id",
        "type",
        "value",
        "lead_investor",
        "funding_round_id",
        "funding_round_value",
        "investor_id",
        "investor_name",
        "investor_type",
        "source_raw",
    ],
    "institution_investments": [
        "institution_id",
        "investment_id",
        "type",
        "value",
        "lead_investor",
        "funding_round_id",
        "funding_round_value",
        "target_id",
        "target_name",
        "target_type",
        "source_raw",
    ],
}


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
    papers: list[dict[str, Any]] = []
    paper_author: list[dict[str, Any]] = []
    paper_institution: list[dict[str, Any]] = []
    paper_yearly_counts: list[dict[str, Any]] = []
    paper_awards: list[dict[str, Any]] = []
    source_raw = response.get("raw_uri", "")

    for item in _items(response):
        paper_id = _id(item, "paper")
        institution_ids = _list(item.get("institution_ids")) or _list(item.get("institution_id"))
        institution_names = _list(item.get("institutions")) or _list(item.get("institution"))
        conf_award_info = item.get("conf_award_info") or {"awards": item.get("awards") or []}
        venue = (
            item.get("conference_abbreviation")
            or item.get("conference_name")
            or item.get("journal_abbreviation")
            or item.get("journal_name")
            or item.get("venue")
            or ""
        )
        papers.append(
            {
                "paper_id": paper_id,
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "first_authors": _jsonish(item.get("first_authors") or []),
                "corresponding_authors": _jsonish(item.get("corresponding_authors") or []),
                "institution": item.get("institution", ""),
                "institution_id": item.get("institution_id", ""),
                "institution_ids": _jsonish(institution_ids),
                "institutions": _jsonish(institution_names),
                "country_code": item.get("country_code", ""),
                "pub_date": item.get("pub_date") or item.get("published_at") or "",
                "venue": venue,
                "journal_name": item.get("journal_name", ""),
                "journal_abbreviation": item.get("journal_abbreviation", ""),
                "conference_name": item.get("conference_name", ""),
                "conference_abbreviation": item.get("conference_abbreviation", ""),
                "conf_award_info": _jsonish(conf_award_info),
                "heat": _heat(item),
                "previous_heat": _previous_heat(item),
                "cited_by_count": item.get("cited_by_count") or item.get("citation_count") or 0,
                "citation_count": item.get("citation_count") or item.get("cited_by_count") or 0,
                "domains": _jsonish(item.get("domains") or item.get("fields") or []),
                "sub_domains": _jsonish(item.get("sub_domains") or []),
                "landing_page_url": item.get("landing_page_url", ""),
                "pdf_url": item.get("pdf_url", ""),
                "count_by_year": _jsonish(item.get("count_by_year") or []),
                "source_raw": source_raw,
            }
        )

        author_objs = item.get("authors") if isinstance(item.get("authors"), list) else []
        for idx, author in enumerate(author_objs):
            paper_author.append(
                {
                    "paper_id": paper_id,
                    "scholar_id": author.get("author_id", ""),
                    "display_name": author.get("display_name", ""),
                    "is_first_author": bool(author.get("is_first_author")),
                    "is_corresponding_author": bool(author.get("is_corresponding_author")),
                    "author_order": idx + 1,
                    "source_raw": source_raw,
                }
            )
        for idx, author_id in enumerate(_list(item.get("author_ids"))):
            paper_author.append(
                {
                    "paper_id": paper_id,
                    "scholar_id": author_id,
                    "display_name": "",
                    "is_first_author": idx == 0,
                    "is_corresponding_author": False,
                    "author_order": idx + 1,
                    "source_raw": source_raw,
                }
            )
        for idx, institution_id in enumerate(institution_ids):
            paper_institution.append(
                {
                    "paper_id": paper_id,
                    "institution_id": institution_id,
                    "institution_name": institution_names[idx] if idx < len(institution_names) else "",
                    "is_primary": institution_id == str(item.get("institution_id", "")),
                    "source_raw": source_raw,
                }
            )
        paper_yearly_counts.extend(_yearly_count_rows("paper_id", paper_id, item.get("count_by_year"), source_raw))
        paper_awards.extend(_award_rows("paper_id", paper_id, conf_award_info, source_raw))
    return {
        "papers": papers,
        "paper_author": paper_author,
        "paper_institution": paper_institution,
        "paper_yearly_counts": paper_yearly_counts,
        "paper_awards": paper_awards,
    }


def normalize_institutions_response(response: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    institutions: list[dict[str, Any]] = []
    institution_awards: list[dict[str, Any]] = []
    institution_venues: list[dict[str, Any]] = []
    source_raw = response.get("raw_uri", "")
    for item in _items(response):
        institution_id = _id(item, "institution")
        radar = item.get("index_radar_display") or {}
        institutions.append(
            {
                "institution_id": institution_id,
                "name": item.get("name", ""),
                "image": item.get("image", ""),
                "full_description": item.get("full_description", ""),
                "country_code": item.get("country_code") or item.get("country") or "",
                "paper_count": item.get("paper_count", 0),
                "author_count": item.get("author_count") or item.get("scholar_count") or 0,
                "scholar_count": item.get("author_count") or item.get("scholar_count") or 0,
                "num_employees": item.get("num_employees", ""),
                "heat": _heat(item),
                "previous_heat": _previous_heat(item),
                "funding_total_usd": item.get("funding_total_usd", ""),
                "domains": _jsonish(item.get("domains") or item.get("fields") or []),
                "sub_tags": _jsonish(item.get("sub_tags") or []),
                "conference_names": _jsonish(item.get("conference_names") or []),
                "journal_names": _jsonish(item.get("journal_names") or []),
                "award_list": _jsonish(item.get("award_list") or item.get("awards") or []),
                "academic_impact": radar.get("academic_impact", ""),
                "capital_signal": radar.get("capital_signal", ""),
                "innovation_power": radar.get("innovation_power", ""),
                "media_momentum": radar.get("media_momentum", ""),
                "talent_momentum": radar.get("talent_momentum", ""),
                "total_score": radar.get("total_score", ""),
                "source_raw": source_raw,
            }
        )
        for award_group in _award_groups(item.get("award_list") or item.get("awards")):
            institution_awards.extend(_award_rows("institution_id", institution_id, award_group, source_raw))
        institution_venues.extend(_venue_rows("institution_id", institution_id, "conference", item.get("conference_names"), source_raw))
        institution_venues.extend(_venue_rows("institution_id", institution_id, "journal", item.get("journal_names"), source_raw))
    return {
        "institutions": institutions,
        "institution_awards": institution_awards,
        "institution_venues": institution_venues,
    }


def normalize_scholars_response(response: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    scholars: list[dict[str, Any]] = []
    scholar_institution: list[dict[str, Any]] = []
    scholar_yearly_counts: list[dict[str, Any]] = []
    scholar_awards: list[dict[str, Any]] = []
    scholar_venues: list[dict[str, Any]] = []
    source_raw = response.get("raw_uri", "")
    for item in _items(response):
        scholar_id = _id(item, "scholar")
        institution_ids = _list(item.get("institution_ids")) or _list(item.get("institution_id"))
        institution_names = _list(item.get("institutions")) or _list(item.get("institution"))
        scholars.append(
            {
                "scholar_id": scholar_id,
                "display_name": item.get("display_name") or item.get("name") or "",
                "avatar": item.get("avatar", ""),
                "institution": item.get("institution", ""),
                "institution_id": item.get("institution_id", ""),
                "institution_ids": _jsonish(institution_ids),
                "institutions": _jsonish(institution_names),
                "cited_by_count": item.get("cited_by_count", ""),
                "count_by_year": _jsonish(item.get("count_by_year") or []),
                "paper_count": item.get("paper_count") or len(_list(item.get("paper_ids"))),
                "first_author_paper_count": item.get("first_author_paper_count", ""),
                "corresponding_paper_count": item.get("corresponding_paper_count", ""),
                "homepage": item.get("homepage", ""),
                "is_ethnic_chinese": item.get("is_ethnic_chinese", ""),
                "heat": _heat(item),
                "previous_heat": _previous_heat(item),
                "domains": _jsonish(item.get("domains") or item.get("fields") or []),
                "sub_domains": _jsonish(item.get("sub_domains") or []),
                "country_code": item.get("country_code", ""),
                "journal_names": _jsonish(item.get("journal_names") or []),
                "journal_abbreviations": _jsonish(item.get("journal_abbreviations") or []),
                "conference_names": _jsonish(item.get("conference_names") or item.get("venues") or []),
                "conference_abbreviations": _jsonish(item.get("conference_abbreviations") or []),
                "award_list": _jsonish(item.get("award_list") or item.get("awards") or []),
                "email": item.get("email", ""),
                "source_raw": source_raw,
            }
        )
        for idx, institution_id in enumerate(institution_ids):
            scholar_institution.append(
                {
                    "scholar_id": scholar_id,
                    "institution_id": institution_id,
                    "institution_name": institution_names[idx] if idx < len(institution_names) else "",
                    "is_primary": institution_id == str(item.get("institution_id", "")),
                    "source_raw": source_raw,
                }
            )
        scholar_yearly_counts.extend(_yearly_count_rows("scholar_id", scholar_id, item.get("count_by_year"), source_raw))
        for award_group in _award_groups(item.get("award_list") or item.get("awards")):
            scholar_awards.extend(_award_rows("scholar_id", scholar_id, award_group, source_raw))
        scholar_venues.extend(_venue_rows("scholar_id", scholar_id, "conference", item.get("conference_names") or item.get("venues"), source_raw))
        scholar_venues.extend(_venue_rows("scholar_id", scholar_id, "journal", item.get("journal_names"), source_raw))
    return {
        "scholars": scholars,
        "scholar_institution": scholar_institution,
        "scholar_yearly_counts": scholar_yearly_counts,
        "scholar_awards": scholar_awards,
        "scholar_venues": scholar_venues,
    }


def normalize_funding_response(response: dict[str, Any], institution_id: str) -> dict[str, list[dict[str, Any]]]:
    data = response.get("data", {})
    source_raw = response.get("raw_uri", "")
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    financials = ((data.get("funding") or {}).get("financials_highlights") or {}) if isinstance(data, dict) else {}
    invested = (data.get("invested") or {}) if isinstance(data, dict) else {}
    funding_total = summary.get("total_funding") or financials.get("funding_total") or {}
    funding_summary = [
        {
            "institution_id": institution_id,
            "total_funding_currency": funding_total.get("currency", ""),
            "total_funding_value": funding_total.get("value", ""),
            "total_funding_value_usd": funding_total.get("value_usd", ""),
            "funding_round_count": summary.get("funding_round_count", financials.get("num_funding_rounds", "")),
            "investor_count": summary.get("investor_count", financials.get("num_investors", "")),
            "lead_investor_count": summary.get("lead_investor_count", financials.get("num_lead_investors", "")),
            "invested_round_count": summary.get("invested_round_count", ""),
            "lead_invested_round_count": summary.get("lead_invested_round_count", ""),
            "investment_count": invested.get("investment_count", ""),
            "lead_investment_count": invested.get("lead_investment_count", ""),
            "source_raw": source_raw,
        }
    ]

    funding_rounds: list[dict[str, Any]] = []
    for idx, item in enumerate(((data.get("funding") or {}).get("funding_rounds") or []) if isinstance(data, dict) else []):
        money = item.get("money_raised") or {}
        funding_rounds.append(
            {
                "funding_id": item.get("id") or f"{institution_id}_funding_{idx + 1}",
                "institution_id": institution_id,
                "uuid": item.get("uuid", ""),
                "title": item.get("title", ""),
                "announced_on": item.get("announced_on", ""),
                "image_id": item.get("image_id", ""),
                "currency": money.get("currency", ""),
                "value": money.get("value", ""),
                "value_usd": money.get("value_usd", ""),
                "lead_investors": _jsonish(item.get("lead_investors") or []),
                "source_raw": source_raw,
            }
        )
    if not funding_rounds:
        funding_rounds.append(
            {
                "funding_id": f"{institution_id}_funding_summary",
                "institution_id": institution_id,
                "uuid": "",
                "title": "Funding summary",
                "announced_on": "",
                "image_id": "",
                "currency": funding_total.get("currency", ""),
                "value": funding_total.get("value", ""),
                "value_usd": funding_total.get("value_usd", ""),
                "lead_investors": "[]",
                "source_raw": source_raw,
            }
        )

    funding_investors: list[dict[str, Any]] = []
    for item in ((data.get("funding") or {}).get("investors") or []) if isinstance(data, dict) else []:
        funding_round = item.get("funding_round") or {}
        investor = item.get("investor") or {}
        funding_investors.append(
            {
                "institution_id": institution_id,
                "investor_record_id": item.get("id", ""),
                "type": item.get("type", ""),
                "value": item.get("value", ""),
                "lead_investor": item.get("lead_investor", ""),
                "funding_round_id": funding_round.get("id", ""),
                "funding_round_value": funding_round.get("value", ""),
                "investor_id": investor.get("id", ""),
                "investor_name": investor.get("value", ""),
                "investor_type": investor.get("type", ""),
                "source_raw": source_raw,
            }
        )

    institution_investments: list[dict[str, Any]] = []
    for item in invested.get("investments") or []:
        funding_round = item.get("funding_round") or {}
        investor = item.get("investor") or {}
        institution_investments.append(
            {
                "institution_id": institution_id,
                "investment_id": item.get("id", ""),
                "type": item.get("type", ""),
                "value": item.get("value", ""),
                "lead_investor": item.get("lead_investor", ""),
                "funding_round_id": funding_round.get("id", ""),
                "funding_round_value": funding_round.get("value", ""),
                "target_id": investor.get("id", ""),
                "target_name": investor.get("value", ""),
                "target_type": investor.get("type", ""),
                "source_raw": source_raw,
            }
        )

    return {
        "funding": funding_rounds,
        "funding_summary": funding_summary,
        "funding_rounds": funding_rounds,
        "funding_investors": funding_investors,
        "institution_investments": institution_investments,
    }


def write_tables(workspace_path: Path, tables: dict[str, list[dict[str, Any]]], append: bool = True) -> None:
    tables_dir = workspace_path / "domains" / "ai_index" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        path = tables_dir / f"{name}.csv"
        merged = _read_csv(path) if append and path.exists() else []
        merged.extend(rows)
        unique = _dedupe(merged)
        _write_csv(path, unique, table_name=name)


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
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)] if value != "" else []


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _award_groups(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return [{"awards": value}]
        return [item for item in value if isinstance(item, dict)]
    return []


def _heat(item: dict[str, Any]) -> Any:
    heat = item.get("heat") or item.get("hotness")
    if isinstance(heat, dict):
        return heat.get("half_year") or heat.get("month") or ""
    return heat if heat is not None else ""


def _previous_heat(item: dict[str, Any]) -> Any:
    heat = item.get("heat") or item.get("hotness")
    if isinstance(heat, dict):
        return heat.get("previous_half_year", "")
    return ""


def _yearly_count_rows(id_field: str, id_value: str, count_by_year: Any, source_raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list_of_dicts(count_by_year):
        rows.append(
            {
                id_field: id_value,
                "year": item.get("year", ""),
                "cited_by_count": item.get("cited_by_count") or item.get("count") or item.get("value") or "",
                "source_raw": source_raw,
            }
        )
    return rows


def _award_rows(id_field: str, id_value: str, award_group: Any, source_raw: str) -> list[dict[str, Any]]:
    if not isinstance(award_group, dict):
        return []
    rows: list[dict[str, Any]] = []
    conf = award_group.get("conf", "")
    year = award_group.get("year", "")
    awards = award_group.get("awards") or []
    if not awards and award_group.get("key"):
        awards = [award_group]
    for award in _award_items(awards):
        rows.append(
            {
                id_field: id_value,
                "conf": conf,
                "year": year,
                "award_key": award.get("key", ""),
                "award_title": award.get("title") or award.get("awards") or "",
                "source_raw": source_raw,
            }
        )
    return rows


def _award_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item if isinstance(item, dict) else {"title": str(item)} for item in value if item not in (None, "")]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value:
        return [{"title": value}]
    return []


def _venue_rows(id_field: str, id_value: str, venue_type: str, venues: Any, source_raw: str) -> list[dict[str, Any]]:
    return [
        {
            id_field: id_value,
            "venue_type": venue_type,
            "venue_name": venue,
            "source_raw": source_raw,
        }
        for venue in _list(venues)
    ]


def _jsonish(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], table_name: str | None = None) -> None:
    rows = list(rows)
    schema = TABLE_SCHEMAS.get(table_name or "", [])
    if not rows:
        if not path.exists():
            path.write_text((",".join(schema) + "\n") if schema else "", encoding="utf-8")
        return
    fields: list[str] = list(schema)
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
