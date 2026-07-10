from datetime import UTC, datetime
from pathlib import Path

from ai_software_factory.models import (
    DiscoveryVerdict,
    HumanDecisionRecord,
    HumanRequestRecord,
    HumanRequestStatus,
    HumanRequestType,
    WorkflowState,
    WorkflowStatus,
)
from ai_software_factory.services import IdentifierService

from .persistence import StateStore
from .routing import assert_transition


class FactoryFlow:
    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path
        self.store = StateStore(repository_path)
        self.ids = IdentifierService(repository_path)

    def start_request(self, raw_request: str) -> WorkflowState:
        state = WorkflowState(
            request_id=self.ids.request_id(),
            repository_path=self.repository_path,
            current_stage=WorkflowStatus.DISCOVERY_RUNNING,
            status=WorkflowStatus.DISCOVERY_RUNNING,
            transition_history=[f"NEW->DISCOVERY_RUNNING: {raw_request}"],
        )
        self.store.save(state)
        return state

    def transition(self, state: WorkflowState, target: WorkflowStatus) -> WorkflowState:
        assert_transition(state.status, target)
        state.transition_history.append(f"{state.status}->{target}")
        state.status = target
        state.current_stage = target
        if target in {
            WorkflowStatus.WAITING_FOR_CLARIFICATION,
            WorkflowStatus.WAITING_FOR_SPEC_APPROVAL,
            WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL,
            WorkflowStatus.WAITING_FOR_BACKLOG_APPROVAL,
            WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
        }:
            self.ensure_human_request(state)
        self._touch(state)
        self.store.save(state)
        return state

    def resume(self, request_id: str) -> WorkflowState:
        state = self.store.load(request_id)
        self.ensure_human_request(state)
        self.store.save(state)
        return state

    def status(self, request_id: str) -> WorkflowState:
        return self.resume(request_id)

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
        state.transition_history.append(
            "WAITING_FOR_CLARIFICATION->WAITING_FOR_SPEC_APPROVAL: ANSWERED"
        )
        state.status = WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
        state.current_stage = WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
        self.ensure_human_request(state)
        self._touch(state)
        self.store.save(state)
        return state

    def approve(self, request_id: str, *, human_request_id: str | None = None) -> WorkflowState:
        return self._decide(
            request_id, DiscoveryVerdict.APPROVED, human_request_id=human_request_id
        )

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

    def ensure_human_request(self, state: WorkflowState) -> HumanRequestRecord | None:
        if state.status == WorkflowStatus.WAITING_FOR_CLARIFICATION:
            return self._create_pending_request(
                state,
                request_type=HumanRequestType.CLARIFICATION,
                question_or_decision="\n".join(state.pending_questions)
                or "Clarification required.",
                valid_options=[],
            )
        if state.status in {
            WorkflowStatus.WAITING_FOR_SPEC_APPROVAL,
            WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL,
            WorkflowStatus.WAITING_FOR_BACKLOG_APPROVAL,
            WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
        }:
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
        if verdict.value not in pending.valid_options:
            raise ValueError("Human decision is not valid for this request")
        pending.status = HumanRequestStatus(verdict.value)
        pending.decisions.append(HumanDecisionRecord(value=verdict.value, answer=answer))
        if verdict is DiscoveryVerdict.APPROVED:
            target = WorkflowStatus.COMPLETED
        elif verdict is DiscoveryVerdict.REJECTED:
            target = WorkflowStatus.REJECTED
        else:
            target = WorkflowStatus.WAITING_FOR_CLARIFICATION
        state.transition_history.append(f"{state.status}->{target}: {verdict.value}")
        state.status = target
        state.current_stage = target
        if target == WorkflowStatus.WAITING_FOR_CLARIFICATION:
            self.ensure_human_request(state)
        self._touch(state)
        self.store.save(state)
        return state

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
        self,
        state: WorkflowState,
        request_type: HumanRequestType,
        human_request_id: str | None,
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
