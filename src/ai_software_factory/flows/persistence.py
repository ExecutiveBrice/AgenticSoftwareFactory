# mypy: ignore-errors
import json
import os
import tempfile
from pathlib import Path

from ai_software_factory.models import WorkflowState


class StateStore:
    def __init__(self, repository_path: Path) -> None:
        self.root = repository_path / ".factory" / "state"
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, request_id: str) -> Path:
        return self.root / f"{request_id}.json"

    def save(self, state: WorkflowState) -> None:
        data = state.model_dump_json(indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=state.request_id, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self.path(state.request_id))

    def load(self, request_id: str) -> WorkflowState:
        return WorkflowState.model_validate(
            json.loads(self.path(request_id).read_text(encoding="utf-8"))
        )
