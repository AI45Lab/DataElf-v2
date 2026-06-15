from __future__ import annotations

from dataelf.schemas import TaskState, now_utc
from dataelf.stores.sqlite_store import SQLiteStore


def verify_report(task_state: TaskState, store: SQLiteStore) -> TaskState:
    evidence = {item.evidence_id: item for item in store.list_evidence(task_state.task_id)}
    claims = store.list_claims(task_state.task_id)
    report = store.get_latest_report(task_state.task_id)

    errors: list[str] = []
    if report is None:
        errors.append("Report is missing.")
    if len(claims) < 2:
        errors.append("Report must have at least 2 claims.")
    if len(evidence) < 3:
        errors.append("Report must have at least 3 evidence items.")
    for claim in claims:
        if not claim.evidence_ids:
            errors.append(f"Claim {claim.claim_id} has no evidence.")
            claim.verification_status = "unsupported"
        elif any(evidence_id not in evidence for evidence_id in claim.evidence_ids):
            errors.append(f"Claim {claim.claim_id} references missing evidence.")
            claim.verification_status = "unsupported"
        else:
            claim.verification_status = "supported"
        store.save_claim(claim)

    if errors:
        task_state.status = "failed"
        task_state.error = " ".join(errors)
    else:
        task_state.status = "completed"
        task_state.error = None
    task_state.updated_at = now_utc()
    store.save_task_state(task_state)
    store.add_trace_event(task_state.task_id, "evidence_verify", {"status": task_state.status, "errors": errors})
    return task_state
