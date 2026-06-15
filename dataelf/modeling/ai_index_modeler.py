from __future__ import annotations

import hashlib
from typing import Any

from dataelf.schemas import DomainObject, DomainRelation, RecordEnvelope


def _object_id(task_id: str, object_type: str, source_id: str) -> str:
    return f"obj_{task_id}_{object_type.lower()}_{source_id}".replace(" ", "_")


def _relation_id(task_id: str, relation_type: str, source_id: str, target_id: str) -> str:
    digest = hashlib.sha1(f"{task_id}:{relation_type}:{source_id}:{target_id}".encode("utf-8")).hexdigest()[:12]
    return f"rel_{digest}"


def _add_object(
    objects: dict[str, DomainObject],
    task_id: str,
    object_type: str,
    source_id: str,
    name: str,
    properties: dict[str, Any],
    record_id: str,
) -> str:
    object_id = _object_id(task_id, object_type, source_id)
    if object_id not in objects:
        props = dict(properties)
        props["source_id"] = source_id
        objects[object_id] = DomainObject(
            object_id=object_id,
            task_id=task_id,
            object_type=object_type,
            name=name,
            properties=props,
            source_record_ids=[record_id],
        )
    else:
        existing = objects[object_id]
        if existing.name == source_id and name != source_id:
            existing.name = name
        existing.properties.update(properties)
        existing.properties["source_id"] = source_id
        if record_id not in existing.source_record_ids:
            existing.source_record_ids.append(record_id)
    return object_id


def _add_relation(
    relations: dict[str, DomainRelation],
    task_id: str,
    relation_type: str,
    source_object_id: str,
    target_object_id: str,
    properties: dict[str, Any],
    record_id: str,
) -> None:
    relation_id = _relation_id(task_id, relation_type, source_object_id, target_object_id)
    if relation_id not in relations:
        relations[relation_id] = DomainRelation(
            relation_id=relation_id,
            task_id=task_id,
            relation_type=relation_type,
            source_object_id=source_object_id,
            target_object_id=target_object_id,
            properties=properties,
            source_record_ids=[record_id],
        )
    elif record_id not in relations[relation_id].source_record_ids:
        relations[relation_id].source_record_ids.append(record_id)


def model_records(records: list[RecordEnvelope]) -> tuple[list[DomainObject], list[DomainRelation]]:
    objects: dict[str, DomainObject] = {}
    relations: dict[str, DomainRelation] = {}

    for record in records:
        payload = record.payload
        if record.source_type == "institution":
            source = _add_object(objects, record.task_id, "Institution", payload["id"], payload["name"], payload, record.record_id)
            for field in payload.get("fields", []):
                field_obj = _add_object(objects, record.task_id, "Field", field, field, {"name": field}, record.record_id)
                _add_relation(relations, record.task_id, "WORKS_ON", source, field_obj, {}, record.record_id)
        elif record.source_type == "paper":
            source = _add_object(objects, record.task_id, "Paper", payload["id"], payload["title"], payload, record.record_id)
            venue = payload.get("venue")
            if venue:
                venue_obj = _add_object(objects, record.task_id, "Venue", venue, venue, {"name": venue}, record.record_id)
                _add_relation(relations, record.task_id, "PUBLISHED_IN", source, venue_obj, {}, record.record_id)
            for field in payload.get("fields", []):
                field_obj = _add_object(objects, record.task_id, "Field", field, field, {"name": field}, record.record_id)
                _add_relation(relations, record.task_id, "RELATED_TO_FIELD", source, field_obj, {}, record.record_id)
            for scholar_id in payload.get("author_ids", []):
                scholar_obj = _add_object(objects, record.task_id, "Scholar", scholar_id, scholar_id, {"source_id": scholar_id}, record.record_id)
                _add_relation(relations, record.task_id, "AUTHORED_BY", source, scholar_obj, {}, record.record_id)
            for inst_id in payload.get("institution_ids", []):
                inst_obj = _add_object(objects, record.task_id, "Institution", inst_id, inst_id, {"source_id": inst_id}, record.record_id)
                _add_relation(relations, record.task_id, "HAS_PAPER", inst_obj, source, {}, record.record_id)
        elif record.source_type == "scholar":
            source = _add_object(objects, record.task_id, "Scholar", payload["id"], payload["name"], payload, record.record_id)
            for field in payload.get("fields", []):
                field_obj = _add_object(objects, record.task_id, "Field", field, field, {"name": field}, record.record_id)
                _add_relation(relations, record.task_id, "WORKS_ON", source, field_obj, {}, record.record_id)
            for inst_id in payload.get("institution_ids", []):
                inst_obj = _add_object(objects, record.task_id, "Institution", inst_id, inst_id, {"source_id": inst_id}, record.record_id)
                _add_relation(relations, record.task_id, "AFFILIATED_WITH", source, inst_obj, {}, record.record_id)

    return list(objects.values()), list(relations.values())
