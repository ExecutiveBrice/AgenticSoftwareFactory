import json
import os
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from ai_software_factory.models import (
    HumanDecisionRecord,
    HumanRequestRecord,
    HumanRequestStatus,
    HumanRequestType,
    WorkflowState,
    WorkflowStatus,
)


class StateStore:
    def __init__(self, repository_path: Path) -> None:
        self.root = repository_path / ".factory" / "state"
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, request_id: str) -> Path:
        return self.root / f"{request_id}.json"

    def save(self, state: WorkflowState) -> None:
        data = json.dumps(_to_jsonable(state), indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=state.request_id, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self.path(state.request_id))

    def load(self, request_id: str) -> WorkflowState:
        payload = json.loads(self.path(request_id).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Workflow state must be a JSON object")
        return _workflow_state_from_json(payload)


def _to_jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return {key: _to_jsonable(item) for key, item in value.model_dump().items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _workflow_state_from_json(payload: dict[str, Any]) -> WorkflowState:
    data = dict(payload)
    data["repository_path"] = Path(str(data["repository_path"]))
    for path_key in ("specification_path",):
        if data.get(path_key) is not None:
            data[path_key] = Path(str(data[path_key]))
    data["design_paths"] = [Path(str(path)) for path in data.get("design_paths", [])]
    data["status"] = WorkflowStatus(str(data.get("status", WorkflowStatus.NEW)))
    data["current_stage"] = WorkflowStatus(str(data.get("current_stage", WorkflowStatus.NEW)))
    data["human_requests"] = [
        _human_request_from_json(item) for item in data.get("human_requests", [])
    ]
    for date_key in ("created_at", "updated_at"):
        if isinstance(data.get(date_key), str):
            data[date_key] = datetime.fromisoformat(data[date_key])
    return WorkflowState.model_validate(data)


def _human_request_from_json(payload: object) -> HumanRequestRecord:
    if not isinstance(payload, dict):
        raise ValueError("Human request must be a JSON object")
    data = dict(payload)
    data["stage"] = WorkflowStatus(str(data["stage"]))
    data["type"] = HumanRequestType(str(data["type"]))
    data["status"] = HumanRequestStatus(str(data["status"]))
    data["artifact_paths"] = [Path(str(path)) for path in data.get("artifact_paths", [])]
    if isinstance(data.get("date"), str):
        data["date"] = datetime.fromisoformat(data["date"])
    data["decisions"] = [_human_decision_from_json(item) for item in data.get("decisions", [])]
    return HumanRequestRecord.model_validate(data)


def _human_decision_from_json(payload: object) -> HumanDecisionRecord:
    if not isinstance(payload, dict):
        raise ValueError("Human decision must be a JSON object")
    data = dict(payload)
    if isinstance(data.get("date"), str):
        data["date"] = datetime.fromisoformat(data["date"])
    return HumanDecisionRecord.model_validate(data)
