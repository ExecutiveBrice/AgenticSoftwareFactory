from datetime import UTC, datetime
from pathlib import Path

from ai_software_factory.models import (
    DesignDecision,
    DevelopmentDecision,
    DiscoveryVerdict,
    FlowTransitionEvent,
    FlowTransitionRecord,
    HumanDecisionRecord,
    HumanRequestRecord,
    HumanRequestStatus,
    HumanRequestType,
    PlanningDecision,
    ProductAcceptanceDecision,
    QAVerdict,
    ReviewVerdict,
    WorkflowState,
    WorkflowStatus,
    WorkflowStep,
)
from ai_software_factory.services import IdentifierService

from .persistence import StateStore
from .routing import assert_transition, route_qa, route_review

_WAITING = {
    WorkflowStatus.WAITING_FOR_CLARIFICATION,
    WorkflowStatus.WAITING_FOR_SPEC_APPROVAL,
    WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL,
    WorkflowStatus.WAITING_FOR_BACKLOG_APPROVAL,
    WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
}


class FactoryFlow:
    def __init__(self, repository_path: Path, *, max_loops: int = 5) -> None:
        self.repository_path = repository_path
        self.max_loops = max_loops
        self.store = StateStore(repository_path)
        self.ids = IdentifierService(repository_path)

    def start_request(self, raw_request: str) -> WorkflowState:
        state = WorkflowState(
            request_id=self.ids.request_id(),
            repository_path=self.repository_path,
            current_stage=WorkflowStatus.DISCOVERY_RUNNING,
            status=WorkflowStatus.DISCOVERY_RUNNING,
            max_loops=self.max_loops,
        )
        self._record(
            state, FlowTransitionEvent.START_REQUEST, WorkflowStatus.NEW, state.status, raw_request
        )
        self.store.save(state)
        return state

    def transition(self, state: WorkflowState, target: WorkflowStatus) -> WorkflowState:
        return self._move(state, target, FlowTransitionEvent.START_REQUEST)

    def resume(self, request_id: str) -> WorkflowState:
        state = self.store.load(request_id)
        self.ensure_human_request(state)
        self.store.save(state)
        return state

    def status(self, request_id: str) -> WorkflowState:
        return self.resume(request_id)

    def record_discovery_questions(self, request_id: str, questions: list[str]) -> WorkflowState:
        state = self.store.load(request_id)
        state.pending_questions = questions
        return self._move(
            state, WorkflowStatus.WAITING_FOR_CLARIFICATION, FlowTransitionEvent.DISCOVERY_QUESTIONS
        )

    def answer(
        self, request_id: str, answer_text: str, *, human_request_id: str | None = None
    ) -> WorkflowState:
        state = self.store.load(request_id)
        if state.status != WorkflowStatus.WAITING_FOR_CLARIFICATION:
            raise ValueError("Clarification answer is not valid for the current workflow status")
        pending = self._pending_request(state, HumanRequestType.CLARIFICATION, human_request_id)
        if state.status != pending.stage:
            raise ValueError("Clarification answer is not valid for the current workflow status")
        pending.status = HumanRequestStatus.ANSWERED
        pending.decisions.append(HumanDecisionRecord(value="ANSWERED", answer=answer_text))
        state.pending_questions = []
        return self._move(
            state, WorkflowStatus.DISCOVERY_RUNNING, FlowTransitionEvent.DISCOVERY_CHANGES_REQUESTED
        )

    def approve(self, request_id: str, *, human_request_id: str | None = None) -> WorkflowState:
        state = self._decide(
            request_id, DiscoveryVerdict.APPROVED, human_request_id=human_request_id
        )
        if state.status == WorkflowStatus.KNOWLEDGE_UPDATING:
            state = self.run_knowledge(state.request_id)
        return state

    def reject(self, request_id: str, *, human_request_id: str | None = None) -> WorkflowState:
        return self._decide(
            request_id, DiscoveryVerdict.REJECTED, human_request_id=human_request_id
        )

    def request_changes(
        self, request_id: str, required_changes: str, *, human_request_id: str | None = None
    ) -> WorkflowState:
        state = self._decide(
            request_id,
            DiscoveryVerdict.CHANGES_REQUESTED,
            answer=required_changes,
            human_request_id=human_request_id,
        )
        state.pending_questions = [required_changes]
        self.store.save(state)
        return state

    def run_knowledge(self, request_id: str) -> WorkflowState:
        state = self.store.load(request_id)
        if state.status != WorkflowStatus.KNOWLEDGE_UPDATING:
            return state
        if WorkflowStep.KNOWLEDGE_BEFORE_DESIGN not in state.completed_steps:
            state.completed_steps.append(WorkflowStep.KNOWLEDGE_BEFORE_DESIGN)
            return self._move(
                state, WorkflowStatus.DESIGN_RUNNING, FlowTransitionEvent.KNOWLEDGE_UPDATED
            )
        if WorkflowStep.KNOWLEDGE_FINAL not in state.completed_steps:
            state.completed_steps.append(WorkflowStep.KNOWLEDGE_FINAL)
            return self._move(
                state,
                WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
                FlowTransitionEvent.KNOWLEDGE_UPDATED,
            )
        return state

    def record_design_decision(self, request_id: str, decision: DesignDecision) -> WorkflowState:
        state = self.store.load(request_id)
        target = {
            DesignDecision.STRUCTURAL_DECISION: WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL,
            DesignDecision.APPROVED: WorkflowStatus.PLANNING_RUNNING,
            DesignDecision.CHANGES_REQUESTED: WorkflowStatus.DESIGN_RUNNING,
            DesignDecision.PRODUCT_DECISION_MISSING: WorkflowStatus.BLOCKED,
        }[decision]
        if target == WorkflowStatus.DESIGN_RUNNING:
            self._count_loop(state)
        return self._move(state, target, FlowTransitionEvent.DESIGN_DECISION, decision.value)

    def record_planning_decision(
        self, request_id: str, decision: PlanningDecision
    ) -> WorkflowState:
        state = self.store.load(request_id)
        target = {
            PlanningDecision.COMPLETED: WorkflowStatus.WAITING_FOR_BACKLOG_APPROVAL,
            PlanningDecision.APPROVED: WorkflowStatus.DEVELOPMENT_RUNNING,
            PlanningDecision.CHANGES_REQUESTED: WorkflowStatus.PLANNING_RUNNING,
            PlanningDecision.REJECTED: WorkflowStatus.REJECTED,
        }[decision]
        if target == WorkflowStatus.PLANNING_RUNNING:
            self._count_loop(state)
        return self._move(state, target, FlowTransitionEvent.PLANNING_DECISION, decision.value)

    def start_development(self, request_id: str, task_ids: list[str]) -> WorkflowState:
        state = self.store.load(request_id)
        if state.status != WorkflowStatus.DEVELOPMENT_RUNNING:
            raise ValueError("Development can start only in DEVELOPMENT_RUNNING")
        if not state.task_ids:
            state.task_ids = task_ids
        state.current_task_id = next(
            (task for task in state.task_ids if task not in state.completed_task_ids), None
        )
        self.store.save(state)
        return state

    def record_development_result(
        self, request_id: str, decision: DevelopmentDecision, *, manifest_valid: bool = True
    ) -> WorkflowState:
        state = self.store.load(request_id)
        if decision is DevelopmentDecision.TASK_SUCCEEDED and not manifest_valid:
            decision = DevelopmentDecision.MANIFEST_INVALID
        target = (
            WorkflowStatus.QA_RUNNING
            if decision is DevelopmentDecision.TASK_SUCCEEDED
            else WorkflowStatus.DEVELOPMENT_RUNNING
        )
        if decision is DevelopmentDecision.FAILED:
            target = WorkflowStatus.FAILED
        if target == WorkflowStatus.DEVELOPMENT_RUNNING:
            self._count_loop(state)
        return self._move(
            state,
            target,
            FlowTransitionEvent.DEVELOPMENT_DECISION,
            decision.value,
            state.current_task_id,
        )

    def record_qa_verdict(
        self, request_id: str, verdict: QAVerdict, *, warnings_need_human: bool = False
    ) -> WorkflowState:
        state = self.store.load(request_id)
        state.qa_verdict = verdict
        target = route_qa(verdict, warnings_need_human)
        if target == WorkflowStatus.DEVELOPMENT_RUNNING:
            self._count_loop(state)
        return self._move(
            state, target, FlowTransitionEvent.QA_VERDICT, verdict.value, state.current_task_id
        )

    def record_review_verdict(self, request_id: str, verdict: ReviewVerdict) -> WorkflowState:
        state = self.store.load(request_id)
        state.review_verdict = verdict
        if (
            verdict in {ReviewVerdict.APPROVED, ReviewVerdict.APPROVED_WITH_FOLLOW_UP}
            and state.current_task_id
        ):
            state.completed_task_ids.append(state.current_task_id)
            state.current_task_id = next(
                (task for task in state.task_ids if task not in state.completed_task_ids), None
            )
        if verdict in {ReviewVerdict.APPROVED, ReviewVerdict.APPROVED_WITH_FOLLOW_UP}:
            target = (
                WorkflowStatus.DEVELOPMENT_RUNNING
                if state.current_task_id
                else route_review(verdict)
            )
        else:
            target = route_review(verdict)
        if verdict is ReviewVerdict.CHANGES_REQUESTED:
            self._count_loop(state)
        return self._move(state, target, FlowTransitionEvent.REVIEW_VERDICT, verdict.value)

    def accept_product(self, request_id: str, decision: ProductAcceptanceDecision) -> WorkflowState:
        target = (
            WorkflowStatus.COMPLETED
            if decision is ProductAcceptanceDecision.ACCEPTED
            else WorkflowStatus.REJECTED
        )
        state = self.store.load(request_id)
        return self._move(state, target, FlowTransitionEvent.PRODUCT_ACCEPTANCE, decision.value)

    def ensure_human_request(self, state: WorkflowState) -> HumanRequestRecord | None:
        if state.status == WorkflowStatus.WAITING_FOR_CLARIFICATION:
            return self._create_pending_request(
                state,
                request_type=HumanRequestType.CLARIFICATION,
                question_or_decision="\n".join(state.pending_questions)
                or "Clarification required.",
                valid_options=[],
            )
        if state.status in _WAITING - {WorkflowStatus.WAITING_FOR_CLARIFICATION}:
            return self._create_pending_request(
                state,
                request_type=HumanRequestType.APPROVAL,
                question_or_decision=f"Decision required for {state.status}.",
                valid_options=[
                    DiscoveryVerdict.APPROVED.value,
                    DiscoveryVerdict.CHANGES_REQUESTED.value,
                    DiscoveryVerdict.REJECTED.value,
                ],
            )
        return None

    def _decide(
        self,
        request_id: str,
        verdict: DiscoveryVerdict,
        *,
        answer: str | None = None,
        human_request_id: str | None = None,
    ) -> WorkflowState:
        state = self.store.load(request_id)
        pending = self._pending_request(state, HumanRequestType.APPROVAL, human_request_id)
        if state.status != pending.stage:
            raise ValueError("Human decision does not match the current workflow stage")
        pending.status = HumanRequestStatus(verdict.value)
        pending.decisions.append(HumanDecisionRecord(value=verdict.value, answer=answer))
        if state.status == WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE:
            target = (
                WorkflowStatus.COMPLETED
                if verdict is DiscoveryVerdict.APPROVED
                else WorkflowStatus.REJECTED
            )
        elif verdict is DiscoveryVerdict.APPROVED:
            target = WorkflowStatus.KNOWLEDGE_UPDATING
        elif verdict is DiscoveryVerdict.REJECTED:
            target = WorkflowStatus.REJECTED
        else:
            target = WorkflowStatus.DISCOVERY_RUNNING
        return self._move(state, target, FlowTransitionEvent(f"DISCOVERY_{verdict.value}"))

    def _move(
        self,
        state: WorkflowState,
        target: WorkflowStatus,
        event: FlowTransitionEvent,
        detail: str | None = None,
        task_id: str | None = None,
    ) -> WorkflowState:
        if state.status == target and target not in {
            WorkflowStatus.DESIGN_RUNNING,
            WorkflowStatus.PLANNING_RUNNING,
            WorkflowStatus.DEVELOPMENT_RUNNING,
        }:
            return state
        assert_transition(state.status, target)
        source = state.status
        state.status = target
        state.current_stage = target
        self._record(state, event, source, target, detail, task_id)
        if target in _WAITING:
            self.ensure_human_request(state)
        self._touch(state)
        self.store.save(state)
        return state

    def _record(
        self,
        state: WorkflowState,
        event: FlowTransitionEvent,
        source: WorkflowStatus,
        target: WorkflowStatus,
        detail: str | None = None,
        task_id: str | None = None,
    ) -> None:
        state.transition_history.append(f"{event.value}:{source}->{target}")
        state.transitions.append(
            FlowTransitionRecord(
                event=event, source=source, target=target, detail=detail, task_id=task_id
            )
        )

    def _count_loop(self, state: WorkflowState) -> None:
        state.loop_count += 1
        if state.loop_count > state.max_loops:
            state.status = WorkflowStatus.FAILED
            state.current_stage = WorkflowStatus.FAILED
            self._touch(state)
            self.store.save(state)
            raise ValueError("Maximum correction loop count exceeded")

    def _create_pending_request(
        self,
        state: WorkflowState,
        *,
        request_type: HumanRequestType,
        question_or_decision: str,
        valid_options: list[str],
    ) -> HumanRequestRecord:
        for request in state.human_requests:
            if request.status == HumanRequestStatus.PENDING and request.stage == state.status:
                return request
        record = HumanRequestRecord(
            id=f"{state.request_id}-HUM-{len(state.human_requests) + 1:04d}",
            request_id=state.request_id,
            stage=state.status,
            type=request_type,
            question_or_decision=question_or_decision,
            valid_options=valid_options,
            context={"repository_path": str(state.repository_path)},
            artifact_paths=[] if state.specification_path is None else [state.specification_path],
        )
        state.human_requests.append(record)
        return record

    def _pending_request(
        self, state: WorkflowState, request_type: HumanRequestType, human_request_id: str | None
    ) -> HumanRequestRecord:
        pending = [
            request
            for request in state.human_requests
            if request.status == HumanRequestStatus.PENDING and request.type == request_type
        ]
        if human_request_id is not None:
            pending = [request for request in pending if request.id == human_request_id]
        if not pending:
            raise ValueError("No matching pending human request")
        if len(pending) > 1 and human_request_id is None:
            raise ValueError("Multiple matching pending human requests require a human request id")
        request = pending[0]
        if request.request_id != state.request_id:
            raise ValueError("Human request belongs to a different workflow request")
        return request

    def _touch(self, state: WorkflowState) -> None:
        state.updated_at = datetime.now(UTC)
