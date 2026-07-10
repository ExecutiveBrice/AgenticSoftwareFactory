from pathlib import Path

import pytest

from ai_software_factory.flows import FactoryFlow
from ai_software_factory.flows.persistence import StateStore
from ai_software_factory.models import (
    DesignDecision,
    DevelopmentDecision,
    DiscoveryVerdict,
    PlanningDecision,
    ProductAcceptanceDecision,
    QAVerdict,
    ReviewVerdict,
    WorkflowStatus,
)


def _approved_design_flow(tmp_path: Path) -> FactoryFlow:
    flow = FactoryFlow(tmp_path)
    state = flow.start_request("generic request")
    state = flow.transition(state, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    flow.approve(state.request_id)
    return flow


def _approved_backlog(tmp_path: Path, task_ids: list[str] | None = None) -> tuple[FactoryFlow, str]:
    flow = _approved_design_flow(tmp_path)
    request_id = next((tmp_path / ".factory" / "state").glob("*.json")).stem
    flow.record_design_decision(request_id, DesignDecision.APPROVED)
    flow.record_planning_decision(request_id, PlanningDecision.COMPLETED)
    flow.record_planning_decision(request_id, PlanningDecision.APPROVED)
    flow.start_development(request_id, task_ids or ["TASK-1"])
    return flow, request_id


def test_complete_nominal_path_reaches_final_acceptance(tmp_path: Path) -> None:
    flow, request_id = _approved_backlog(tmp_path)
    flow.record_development_result(request_id, DevelopmentDecision.TASK_SUCCEEDED)
    flow.record_qa_verdict(request_id, QAVerdict.PASSED)
    flow.record_review_verdict(request_id, ReviewVerdict.APPROVED)
    flow.run_knowledge(request_id)
    completed = flow.accept_product(request_id, ProductAcceptanceDecision.ACCEPTED)

    assert completed.status == WorkflowStatus.COMPLETED
    assert [transition.event for transition in completed.transitions]


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (DiscoveryVerdict.CHANGES_REQUESTED, WorkflowStatus.DISCOVERY_RUNNING),
        (DiscoveryVerdict.REJECTED, WorkflowStatus.REJECTED),
    ],
)
def test_discovery_rejection_routes(
    tmp_path: Path, verdict: DiscoveryVerdict, expected: WorkflowStatus
) -> None:
    flow = FactoryFlow(tmp_path)
    state = flow.transition(
        flow.start_request("generic request"), WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
    )

    if verdict is DiscoveryVerdict.CHANGES_REQUESTED:
        routed = flow.request_changes(state.request_id, "generic change")
    else:
        routed = flow.reject(state.request_id)

    assert routed.status == expected


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (DesignDecision.STRUCTURAL_DECISION, WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL),
        (DesignDecision.CHANGES_REQUESTED, WorkflowStatus.DESIGN_RUNNING),
        (DesignDecision.PRODUCT_DECISION_MISSING, WorkflowStatus.BLOCKED),
    ],
)
def test_design_routes(tmp_path: Path, decision: DesignDecision, expected: WorkflowStatus) -> None:
    flow = _approved_design_flow(tmp_path)
    request_id = next((tmp_path / ".factory" / "state").glob("*.json")).stem

    assert flow.record_design_decision(request_id, decision).status == expected


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (PlanningDecision.CHANGES_REQUESTED, WorkflowStatus.PLANNING_RUNNING),
        (PlanningDecision.REJECTED, WorkflowStatus.REJECTED),
    ],
)
def test_planning_rejection_routes(
    tmp_path: Path, decision: PlanningDecision, expected: WorkflowStatus
) -> None:
    flow = _approved_design_flow(tmp_path)
    request_id = next((tmp_path / ".factory" / "state").glob("*.json")).stem
    flow.record_design_decision(request_id, DesignDecision.APPROVED)

    assert flow.record_planning_decision(request_id, decision).status == expected


def test_qa_failed_then_correction(tmp_path: Path) -> None:
    flow, request_id = _approved_backlog(tmp_path)
    flow.record_development_result(request_id, DevelopmentDecision.TASK_SUCCEEDED)
    failed = flow.record_qa_verdict(request_id, QAVerdict.FAILED)
    assert failed.status == WorkflowStatus.DEVELOPMENT_RUNNING

    flow.record_development_result(request_id, DevelopmentDecision.TASK_SUCCEEDED)
    assert (
        flow.record_qa_verdict(request_id, QAVerdict.PASSED).status == WorkflowStatus.REVIEW_RUNNING
    )


def test_review_changes_requested_routes_to_development(tmp_path: Path) -> None:
    flow, request_id = _approved_backlog(tmp_path)
    flow.record_development_result(request_id, DevelopmentDecision.TASK_SUCCEEDED)
    flow.record_qa_verdict(request_id, QAVerdict.PASSED)

    assert (
        flow.record_review_verdict(request_id, ReviewVerdict.CHANGES_REQUESTED).status
        == WorkflowStatus.DEVELOPMENT_RUNNING
    )


def test_review_rejected_routes_to_design(tmp_path: Path) -> None:
    flow, request_id = _approved_backlog(tmp_path)
    flow.record_development_result(request_id, DevelopmentDecision.TASK_SUCCEEDED)
    flow.record_qa_verdict(request_id, QAVerdict.PASSED)

    assert (
        flow.record_review_verdict(request_id, ReviewVerdict.REJECTED).status
        == WorkflowStatus.DESIGN_RUNNING
    )


def test_loop_limit_fails_fast(tmp_path: Path) -> None:
    flow = FactoryFlow(tmp_path, max_loops=1)
    state = flow.start_request("generic request")
    state = flow.transition(state, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    state = flow.approve(state.request_id)
    flow.record_design_decision(state.request_id, DesignDecision.CHANGES_REQUESTED)

    with pytest.raises(ValueError, match="Maximum correction loop"):
        flow.record_design_decision(state.request_id, DesignDecision.CHANGES_REQUESTED)


def test_resume_and_idempotent_waiting_request(tmp_path: Path) -> None:
    flow = FactoryFlow(tmp_path)
    state = flow.transition(
        flow.start_request("generic request"), WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
    )
    first_count = len(state.human_requests)

    resumed = FactoryFlow(tmp_path).resume(state.request_id)
    resumed_again = FactoryFlow(tmp_path).resume(state.request_id)

    assert len(resumed.human_requests) == first_count
    assert len(resumed_again.human_requests) == first_count


def test_invalid_transition_is_rejected(tmp_path: Path) -> None:
    flow = FactoryFlow(tmp_path)
    state = flow.start_request("generic request")

    with pytest.raises(ValueError, match="Invalid transition"):
        flow.transition(state, WorkflowStatus.COMPLETED)


def test_multiple_tasks_are_processed_one_at_a_time(tmp_path: Path) -> None:
    flow, request_id = _approved_backlog(tmp_path, ["TASK-1", "TASK-2"])
    assert StateStore(tmp_path).load(request_id).current_task_id == "TASK-1"

    flow.record_development_result(request_id, DevelopmentDecision.TASK_SUCCEEDED)
    flow.record_qa_verdict(request_id, QAVerdict.PASSED)
    first_review = flow.record_review_verdict(request_id, ReviewVerdict.APPROVED)

    assert first_review.status == WorkflowStatus.DEVELOPMENT_RUNNING
    assert first_review.current_task_id == "TASK-2"


def test_invalid_manifest_does_not_reach_qa(tmp_path: Path) -> None:
    flow, request_id = _approved_backlog(tmp_path)

    routed = flow.record_development_result(
        request_id, DevelopmentDecision.TASK_SUCCEEDED, manifest_valid=False
    )

    assert routed.status == WorkflowStatus.DEVELOPMENT_RUNNING
