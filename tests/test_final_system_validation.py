from pathlib import Path

import pytest

from ai_software_factory.crews import CrewRunRequest, CrewRunResult, FakeCrewRuntime, TaskRunResult
from ai_software_factory.crews.design import DesignCrew
from ai_software_factory.crews.development import DevelopmentCrew
from ai_software_factory.crews.discovery import DiscoveryCrew
from ai_software_factory.crews.knowledge import KnowledgeCrew
from ai_software_factory.crews.planning import PlanningCrew
from ai_software_factory.crews.qa import QaCrew
from ai_software_factory.crews.review import ReviewCrew
from ai_software_factory.flows import FactoryFlow
from ai_software_factory.flows.persistence import StateStore
from ai_software_factory.models import (
    AcceptanceMatrixRow,
    CrewExecutionStatus,
    DesignDecision,
    DevelopmentDecision,
    PlanningDecision,
    ProductAcceptanceDecision,
    QAVerdict,
    ReviewVerdict,
    WorkflowStatus,
)
from ai_software_factory.services import ArtifactService, policy_for_crew


class StructuredFakeRuntime(FakeCrewRuntime):
    def run(self, request: CrewRunRequest) -> CrewRunResult:
        self.requests.append(request)
        results: list[TaskRunResult] = []
        for task in request.definition.tasks:
            payload: dict[str, object] | None = None
            if task.id == "prepare_implementation_manifest":
                payload = {
                    "task_id": request.inputs.get("task_id", "TASK-1"),
                    "changed_files": ["project/target.md"],
                    "tests_added_or_updated": ["tests/test_final_system_validation.py"],
                    "commands_run": ["pytest"],
                    "residual_risks": [],
                }
            elif task.id == "write_qa_report":
                payload = {
                    "verdict": QAVerdict.PASSED.value,
                    "tested_scope": ["TASK-1"],
                    "evidence": ["fake runtime evidence"],
                    "acceptance_matrix": [
                        AcceptanceMatrixRow(
                            criterion="Generic criterion",
                            test="Deterministic fake runtime test",
                            evidence="QA PASSED",
                        ).model_dump()
                    ],
                    "failures": [],
                    "warnings": [],
                    "follow_up": [],
                }
            elif task.id == "issue_final_review":
                payload = {
                    "verdict": ReviewVerdict.APPROVED.value,
                    "reviewed_scope": ["TASK-1"],
                    "findings": ["No blocking findings"],
                    "required_changes": [],
                    "follow_up": [],
                }
            elif task.id == "validate_task_graph":
                payload = {
                    "tasks": [
                        {
                            "id": "TASK-1",
                            "title": "Simulated generic task",
                            "verification": "QA and review pass",
                            "depends_on": [],
                        }
                    ]
                }
            results.append(
                TaskRunResult(
                    task_id=task.id,
                    output=f"deterministic output for {request.crew_id}.{task.id}",
                    status=CrewExecutionStatus.COMPLETED,
                    pydantic_output=payload,
                )
            )
        return CrewRunResult(
            crew_id=request.crew_id,
            status=CrewExecutionStatus.COMPLETED,
            task_results=results,
            final_output=results[-1].output,
            message="Structured fake runtime completed without network access.",
        )


def test_final_e2e_workflow_with_fake_runtime(tmp_path: Path) -> None:
    (tmp_path / ".factory.yaml").write_text("# configuration\n", encoding="utf-8")
    (tmp_path / "project").mkdir()

    flow = FactoryFlow(tmp_path)
    state = flow.start_request("generic request")
    state = flow.record_discovery_questions(state.request_id, ["Clarify generic scope?"])
    state = flow.answer(state.request_id, "Keep the scope minimal.")
    state = flow.transition(state, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    state = flow.approve(state.request_id)
    assert state.status == WorkflowStatus.DESIGN_RUNNING

    state = flow.record_design_decision(state.request_id, DesignDecision.APPROVED)
    state = flow.record_planning_decision(state.request_id, PlanningDecision.COMPLETED)
    state = flow.record_planning_decision(state.request_id, PlanningDecision.APPROVED)
    state = flow.start_development(state.request_id, ["TASK-1"])
    assert state.current_task_id == "TASK-1"

    state = flow.record_development_result(state.request_id, DevelopmentDecision.TASK_SUCCEEDED)
    state = flow.record_qa_verdict(state.request_id, QAVerdict.PASSED)
    state = flow.record_review_verdict(state.request_id, ReviewVerdict.APPROVED)
    state = flow.run_knowledge(state.request_id)
    state = flow.accept_product(state.request_id, ProductAcceptanceDecision.ACCEPTED)

    assert state.status == WorkflowStatus.COMPLETED
    assert StateStore(tmp_path).load(state.request_id).status == WorkflowStatus.COMPLETED


def test_final_route_scenarios_and_resume(tmp_path: Path) -> None:
    flow = FactoryFlow(tmp_path)
    state = flow.start_request("generic request")
    state = flow.transition(state, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    resumed = FactoryFlow(tmp_path).resume(state.request_id)
    assert resumed.human_requests[0].status == "PENDING"

    assert flow.reject(state.request_id).status == WorkflowStatus.REJECTED

    flow = FactoryFlow(tmp_path / "qa")
    state = flow.start_request("generic request")
    flow.transition(state, WorkflowStatus.WAITING_FOR_SPEC_APPROVAL)
    flow.approve(state.request_id)
    flow.record_design_decision(state.request_id, DesignDecision.APPROVED)
    flow.record_planning_decision(state.request_id, PlanningDecision.COMPLETED)
    flow.record_planning_decision(state.request_id, PlanningDecision.APPROVED)
    flow.start_development(state.request_id, ["TASK-1"])
    flow.record_development_result(state.request_id, DevelopmentDecision.TASK_SUCCEEDED)
    assert (
        flow.record_qa_verdict(state.request_id, QAVerdict.FAILED).status
        == WorkflowStatus.DEVELOPMENT_RUNNING
    )
    flow.record_development_result(state.request_id, DevelopmentDecision.TASK_SUCCEEDED)
    flow.record_qa_verdict(state.request_id, QAVerdict.PASSED)
    assert (
        flow.record_review_verdict(state.request_id, ReviewVerdict.CHANGES_REQUESTED).status
        == WorkflowStatus.DEVELOPMENT_RUNNING
    )


def test_all_seven_crews_produce_artifacts_with_fake_runtime(tmp_path: Path) -> None:
    runtime = StructuredFakeRuntime()
    crews = [
        (DiscoveryCrew(tmp_path, runtime=runtime), {}),
        (KnowledgeCrew(tmp_path, runtime=runtime), {}),
        (
            DesignCrew(tmp_path, runtime=runtime),
            {"request_id": "REQ-1", "specification_approved": "true"},
        ),
        (
            PlanningCrew(tmp_path, runtime=runtime),
            {"request_id": "REQ-1", "design_approved": "true"},
        ),
        (
            DevelopmentCrew(tmp_path, task_paths=("project/target.md",), runtime=runtime),
            {"task_id": "TASK-1", "single_task": "true"},
        ),
        (QaCrew(tmp_path, runtime=runtime), {"task_id": "TASK-1"}),
        (
            ReviewCrew(tmp_path, runtime=runtime),
            {"request_id": "REQ-1", "qa_verdict": QAVerdict.PASSED.value},
        ),
    ]

    for crew, inputs in crews:
        result = crew.kickoff(**inputs)
        assert result.status == CrewExecutionStatus.COMPLETED
        assert result.artifacts, crew.crew_id


def test_forbidden_write_is_denied(tmp_path: Path) -> None:
    service = ArtifactService(tmp_path, policy=policy_for_crew("qa"))

    with pytest.raises(PermissionError):
        service.write_text("project/context.md", "forbidden")
