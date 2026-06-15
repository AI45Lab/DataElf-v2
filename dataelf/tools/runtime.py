from __future__ import annotations

import logging
from typing import Any

from dataelf.analysis.trend import analyze_institution_hotness_growth
from dataelf.connectors.ai_index_fixture import FixtureAIIndexConnector
from dataelf.modeling.ai_index_modeler import model_records
from dataelf.schemas import Claim, Evidence, RawArtifact, RecordEnvelope, Report, ToolCall, new_id, now_utc
from dataelf.stores.raw_cache import RawCache
from dataelf.stores.sqlite_store import SQLiteStore

logger = logging.getLogger("dataelf")


class ToolRuntime:
    def __init__(self, store: SQLiteStore, raw_cache: RawCache, connector: FixtureAIIndexConnector):
        self.store = store
        self.raw_cache = raw_cache
        self.connector = connector

    def run_tool(self, task_id: str, tool_name: str, input: dict[str, Any]) -> dict[str, Any]:
        tool_call = ToolCall(tool_call_id=new_id("tool"), task_id=task_id, tool_name=tool_name, input=input)
        self.store.save_tool_call(tool_call)
        self.store.add_trace_event(task_id, "tool_start", {"tool_call_id": tool_call.tool_call_id, "tool_name": tool_name, "input": input})
        logger.info("tool start: %s task=%s", tool_name, task_id)
        try:
            output = self._dispatch(task_id, tool_call.tool_call_id, tool_name, input)
            tool_call.status = "success"
            tool_call.ended_at = now_utc()
            tool_call.output_preview = str(output)[:500]
            self.store.save_tool_call(tool_call, output=output)
            self.store.add_trace_event(task_id, "tool_success", {"tool_call_id": tool_call.tool_call_id, "tool_name": tool_name})
            logger.info("tool success: %s task=%s", tool_name, task_id)
            return output
        except Exception as exc:
            tool_call.status = "failed"
            tool_call.error = str(exc)
            tool_call.ended_at = now_utc()
            self.store.save_tool_call(tool_call)
            self.store.add_trace_event(task_id, "tool_failed", {"tool_call_id": tool_call.tool_call_id, "tool_name": tool_name, "error": str(exc)})
            logger.exception("tool failed: %s task=%s", tool_name, task_id)
            raise

    def _dispatch(self, task_id: str, tool_call_id: str, tool_name: str, input: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "search_records": self._search_records,
            "fetch_records": self._fetch_records,
            "model_records": self._model_records,
            "analyze_trend": self._analyze_trend,
            "write_evidence": self._write_evidence,
            "draft_report": self._draft_report,
        }
        if tool_name not in handlers:
            raise ValueError(f"Unknown DataElf tool: {tool_name}")
        return handlers[tool_name](task_id, tool_call_id, input)

    def _search_records(self, task_id: str, tool_call_id: str, input: dict[str, Any]) -> dict[str, Any]:
        record_type = _normalize_record_type(input.get("record_type", "institution"))
        field = input.get("field", "AI Agent")
        time_window = input.get("time_window", "half_year")
        response = {
            "institution": self.connector.search_institutions,
            "paper": self.connector.search_papers,
            "scholar": self.connector.search_scholars,
        }[record_type](field=field, time_window=time_window)
        raw = self._persist_raw(task_id, response)
        records = self._normalize_records(task_id, record_type, response, raw.raw_id)
        self.store.save_records(records)
        return {
            "record_type": record_type,
            "record_ids": [record.record_id for record in records],
            "previews": [_preview(record) for record in records],
        }

    def _fetch_records(self, task_id: str, tool_call_id: str, input: dict[str, Any]) -> dict[str, Any]:
        record_type = _normalize_record_type(input.get("record_type", "institution"))
        ids = self._resolve_source_ids(record_type, _as_list(input.get("ids", [])))
        methods = {
            "institution": self.connector.fetch_institution,
            "paper": self.connector.fetch_paper,
            "scholar": self.connector.fetch_scholar,
        }
        records: list[RecordEnvelope] = []
        for source_id in ids:
            response = methods[record_type](source_id)
            raw = self._persist_raw(task_id, response)
            records.extend(self._normalize_records(task_id, record_type, response, raw.raw_id))
        self.store.save_records(records)
        return {
            "record_type": record_type,
            "record_ids": [record.record_id for record in records],
            "details": [_preview(record, detailed=True) for record in records],
        }

    def _model_records(self, task_id: str, tool_call_id: str, input: dict[str, Any]) -> dict[str, Any]:
        record_ids = _as_list(input.get("record_ids", []))
        records = self.store.get_records(record_ids)
        objects, relations = model_records(records)
        self.store.save_domain_objects(objects)
        self.store.save_domain_relations(relations)
        return {
            "object_ids": [obj.object_id for obj in objects],
            "relation_ids": [rel.relation_id for rel in relations],
            "object_count": len(objects),
            "relation_count": len(relations),
        }

    def _analyze_trend(self, task_id: str, tool_call_id: str, input: dict[str, Any]) -> dict[str, Any]:
        field = input.get("field", "AI Agent")
        target = input.get("target", "institution_hotness_growth")
        top_k = int(input.get("top_k", 5))
        if target != "institution_hotness_growth":
            raise ValueError(f"Unsupported trend target: {target}")
        objects = self.store.list_domain_objects(task_id, "Institution")
        result = analyze_institution_hotness_growth(objects, field=field, top_k=top_k) if objects else analyze_institution_hotness_growth(self.store.list_records(task_id, "institution"), field=field, top_k=top_k)
        return result

    def _write_evidence(self, task_id: str, tool_call_id: str, input: dict[str, Any]) -> dict[str, Any]:
        source_ids = _as_list(input.get("source_ids", []))
        if not source_ids:
            raise ValueError("write_evidence requires at least one source_id for lineage.")
        evidence = Evidence(
            evidence_id=new_id("evid"),
            task_id=task_id,
            title=str(input["title"]),
            evidence_type=input.get("evidence_type", "metric"),
            summary=str(input["summary"]),
            payload=input.get("payload", {}),
            source_ids=source_ids,
            created_by_tool_call_id=tool_call_id,
            confidence=float(input.get("confidence", 1.0)),
        )
        self.store.save_evidence(evidence)
        return {"evidence_id": evidence.evidence_id, "title": evidence.title}

    def _draft_report(self, task_id: str, tool_call_id: str, input: dict[str, Any]) -> dict[str, Any]:
        claims_input = input.get("claims", [])
        claim_ids: list[str] = []
        for item in claims_input:
            claim = Claim(
                claim_id=new_id("claim"),
                task_id=task_id,
                text=str(item["text"]),
                evidence_ids=_as_list(item.get("evidence_ids", [])),
            )
            self.store.save_claim(claim)
            claim_ids.append(claim.claim_id)
        report = Report(
            report_id=new_id("report"),
            task_id=task_id,
            title=str(input["title"]),
            markdown=str(input["markdown"]),
            claim_ids=claim_ids,
            evidence_ids=_as_list(input.get("evidence_ids", [])),
        )
        self.store.save_report(report)
        return {"report_id": report.report_id, "claim_ids": claim_ids, "evidence_ids": report.evidence_ids}

    def _persist_raw(self, task_id: str, response: dict[str, Any]) -> RawArtifact:
        digest, path = self.raw_cache.write_json(response)
        artifact = RawArtifact(
            raw_id=f"raw_{digest[:16]}",
            task_id=task_id,
            connector=response["source"],
            endpoint=response["endpoint"],
            request=response["request"],
            content_hash=digest,
            content_uri=str(path),
        )
        self.store.save_raw_artifact(artifact)
        return artifact

    def _normalize_records(self, task_id: str, record_type: str, response: dict[str, Any], raw_id: str) -> list[RecordEnvelope]:
        return [
            RecordEnvelope(
                record_id=f"rec_{task_id}_{record_type}_{item['id']}",
                task_id=task_id,
                source=response["source"],
                source_type=record_type,
                source_id=item["id"],
                payload=item,
                raw_id=raw_id,
            )
            for item in response["data"]
        ]

    def _resolve_source_ids(self, record_type: str, ids: list[str]) -> list[str]:
        resolved: list[str] = []
        for item_id in ids:
            if item_id.startswith("rec_"):
                records = self.store.get_records([item_id])
                if records:
                    resolved.append(records[0].source_id)
                    continue
                marker = f"_{record_type}_"
                if marker in item_id:
                    resolved.append(item_id.split(marker, 1)[1])
                    continue
            resolved.append(item_id)
        return resolved


def _normalize_record_type(value: str) -> str:
    normalized = value.strip().lower().rstrip("s")
    aliases = {"institution": "institution", "paper": "paper", "scholar": "scholar"}
    if normalized not in aliases:
        raise ValueError('record_type must be one of "institution", "paper", "scholar"')
    return aliases[normalized]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value)]


def _preview(record: RecordEnvelope, detailed: bool = False) -> dict[str, Any]:
    payload = record.payload
    hotness = payload.get("hotness", {})
    base = {
        "record_id": record.record_id,
        "source_id": record.source_id,
        "name": payload.get("name") or payload.get("title"),
        "fields": payload.get("fields", []),
        "half_year": hotness.get("half_year"),
        "previous_half_year": hotness.get("previous_half_year"),
    }
    if detailed:
        base["related_paper_ids"] = payload.get("related_paper_ids", payload.get("paper_ids", []))
        base["related_scholar_ids"] = payload.get("related_scholar_ids", payload.get("author_ids", []))
        base["news"] = payload.get("news", [])
        base["awards"] = payload.get("awards", [])
    return base
