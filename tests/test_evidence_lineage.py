from __future__ import annotations

from pathlib import Path

from dataelf.schemas import Claim, DomainObject, Evidence, RecordEnvelope, Report
from dataelf.stores.sqlite_store import SQLiteStore
from dataelf.verifier.evidence_verifier import verify_report


def test_evidence_lineage_and_verifier(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "dataelf.sqlite")
    store.init_schema()
    task_id = "task_lineage"
    record = RecordEnvelope(
        record_id="rec_openagent",
        task_id=task_id,
        source="fixture",
        source_type="institution",
        source_id="inst_openagent_lab",
        payload={"id": "inst_openagent_lab", "name": "OpenAgent Lab", "fields": ["AI Agent"]},
    )
    store.save_records([record])
    obj = DomainObject(
        object_id="obj_openagent",
        task_id=task_id,
        object_type="Institution",
        name="OpenAgent Lab",
        properties={"source_id": "inst_openagent_lab"},
        source_record_ids=[record.record_id],
    )
    store.save_domain_objects([obj])
    evidences = [
        Evidence(evidence_id="evid_1", task_id=task_id, title="growth", evidence_type="metric", summary="growth", payload={}, source_ids=[record.record_id, obj.object_id]),
        Evidence(evidence_id="evid_2", task_id=task_id, title="papers", evidence_type="aggregate", summary="papers", payload={}, source_ids=[record.record_id]),
        Evidence(evidence_id="evid_3", task_id=task_id, title="scholars", evidence_type="aggregate", summary="scholars", payload={}, source_ids=[obj.object_id]),
    ]
    for evidence in evidences:
        store.save_evidence(evidence)
    state = store.get_task_state(task_id)
    if state is None:
        from dataelf.schemas import TaskState

        state = TaskState(task_id=task_id, user_query="test", status="running")
        store.save_task_state(state)
    claim_1 = Claim(claim_id="claim_1", task_id=task_id, text="OpenAgent Lab ranks first.", evidence_ids=["evid_1"])
    claim_2 = Claim(claim_id="claim_2", task_id=task_id, text="The result has supporting signals.", evidence_ids=["evid_2", "evid_3"])
    store.save_claim(claim_1)
    store.save_claim(claim_2)
    store.save_report(
        Report(
            report_id="report_1",
            task_id=task_id,
            title="report",
            markdown="# report",
            claim_ids=["claim_1", "claim_2"],
            evidence_ids=["evid_1", "evid_2", "evid_3"],
        )
    )

    verified = verify_report(state, store)
    assert verified.status == "completed"
    assert store.list_evidence(task_id)[0].source_ids == [record.record_id, obj.object_id]
    assert {claim.verification_status for claim in store.list_claims(task_id)} == {"supported"}
    store.close()
