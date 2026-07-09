# mypy: ignore-errors
from pathlib import Path

from ai_software_factory.models import WorkflowState
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
            current_stage="DISCOVERY_RUNNING",
            status="DISCOVERY_RUNNING",
            transition_history=[f"NEW->DISCOVERY_RUNNING: {raw_request}"],
        )
        self.store.save(state)
        return state

    def transition(self, state: WorkflowState, target: str) -> WorkflowState:
        assert_transition(state.status, target)
        state.transition_history.append(f"{state.status}->{target}")
        state.status = target
        state.current_stage = target
        self.store.save(state)
        return state

    def resume(self, request_id: str) -> WorkflowState:
        return self.store.load(request_id)
