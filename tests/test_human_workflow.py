import json
from pathlib import Path

import pytest

from ai_software_factory.flows import FactoryFlow
from ai_software_factory.flows.persistence import StateStore
from ai_software_factory.models import (
    HumanRequestRecord,
    HumanRequestStatus,
    WorkflowState,
    WorkflowStatus,
)


def _state(tmp_path: Path, status: WorkflowStatus) -> WorkflowState:
    flow = FactoryFlow(tmp_path)
    state = flow.start_request("generic request")
    return flow.transition(state, status)


def test_clarification_answer_is_persisted_and_resumes_to_approval(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_CLARIFICATION)

    resumed = FactoryFlow(tmp_path).answer(state.request_id, "generic answer")

    assert resumed.status == WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
    assert resumed.pending_questions == []
    assert resumed.human_requests[0].status == HumanRequestStatus.ANSWERED
    assert resumed.human_requests[0].decisions[0].answer == "generic answer"
    assert (
        StateStore(tmp_path).load(state.request_id).status
        == WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
    )


def test_approval_is_persisted_and_completes_workflow(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)

    approved = FactoryFlow(tmp_path).approve(state.request_id)

    assert approved.status == WorkflowStatus.COMPLETED
    assert approved.human_requests[0].status == HumanRequestStatus.APPROVED


def test_change_request_is_persisted_and_waits_for_clarification(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)

    changed = FactoryFlow(tmp_path).request_changes(state.request_id, "adjust generic scope")

    assert changed.status == WorkflowStatus.WAITING_FOR_CLARIFICATION
    assert changed.pending_questions == ["adjust generic scope"]
    assert changed.human_requests[0].status == HumanRequestStatus.CHANGES_REQUESTED
    assert changed.human_requests[1].status == HumanRequestStatus.PENDING


def test_rejection_is_persisted(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)

    rejected = FactoryFlow(tmp_path).reject(state.request_id)

    assert rejected.status == WorkflowStatus.REJECTED
    assert rejected.human_requests[0].status == HumanRequestStatus.REJECTED


def test_double_response_is_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    FactoryFlow(tmp_path).approve(state.request_id)

    with pytest.raises(ValueError, match="No matching pending"):
        FactoryFlow(tmp_path).approve(state.request_id)


def test_resume_after_restart_preserves_pending_human_request(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)

    resumed = FactoryFlow(tmp_path).resume(state.request_id)

    assert resumed.human_requests[0].id == state.human_requests[0].id
    assert resumed.human_requests[0].status == HumanRequestStatus.PENDING


def test_corrupted_state_is_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    path = StateStore(tmp_path).path(state.request_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["human_requests"][0]["status"] = "BROKEN"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        StateStore(tmp_path).load(state.request_id)


def test_wrong_transition_is_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)

    with pytest.raises(ValueError, match="Clarification answer"):
        FactoryFlow(tmp_path).answer(state.request_id, "not expected")


def test_two_independent_requests_require_matching_human_request_id(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    state.human_requests.append(
        HumanRequestRecord(
            id=f"{state.request_id}-HUM-extra",
            request_id=state.request_id,
            stage=WorkflowStatus.WAITING_FOR_SPEC_APPROVAL,
            type="APPROVAL",
            question_or_decision="Second independent decision",
            valid_options=["APPROVED", "CHANGES_REQUESTED", "REJECTED"],
        )
    )
    StateStore(tmp_path).save(state)

    with pytest.raises(ValueError, match="Multiple matching"):
        FactoryFlow(tmp_path).approve(state.request_id)

    decided = FactoryFlow(tmp_path).approve(
        state.request_id, human_request_id=f"{state.request_id}-HUM-extra"
    )

    assert decided.status == WorkflowStatus.COMPLETED
    assert decided.human_requests[1].status == HumanRequestStatus.APPROVED


def test_wrong_request_id_is_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    state.human_requests[0].request_id = "REQ-other"
    StateStore(tmp_path).save(state)

    with pytest.raises(ValueError, match="different workflow request"):
        FactoryFlow(tmp_path).approve(state.request_id, human_request_id=state.human_requests[0].id)
