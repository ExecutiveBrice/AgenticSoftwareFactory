from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from ai_software_factory.models import CrewDefinition, CrewExecutionStatus
from pydantic import BaseModel, ConfigDict, Field


class TaskRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str
    output: str = ""
    status: CrewExecutionStatus = CrewExecutionStatus.COMPLETED
    message: str = ""


class CrewRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    crew_id: str
    repository_path: Path
    definition: CrewDefinition
    inputs: dict[str, str] = Field(default_factory=dict)


class CrewRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    crew_id: str
    status: CrewExecutionStatus
    task_results: list[TaskRunResult] = Field(default_factory=list)
    message: str = ""


class CrewRuntime(Protocol):
    def run(self, request: CrewRunRequest) -> CrewRunResult:
        """Execute a crew through an adapter and return a typed result."""


class CrewRuntimeFactory(Protocol):
    def create(self, crew_id: str) -> CrewRuntime:
        """Return the runtime to use for a crew."""


class FakeCrewRuntime:
    """Deterministic runtime used by tests without any external service."""

    def __init__(self, *, result: CrewRunResult | None = None) -> None:
        self._result = result
        self.requests: list[CrewRunRequest] = []

    def run(self, request: CrewRunRequest) -> CrewRunResult:
        self.requests.append(request)
        if self._result is not None:
            return self._result
        return CrewRunResult(
            crew_id=request.crew_id,
            status=CrewExecutionStatus.COMPLETED,
            task_results=[
                TaskRunResult(
                    task_id=task.id,
                    output=f"fake output for {request.crew_id}.{task.id}",
                    status=CrewExecutionStatus.COMPLETED,
                )
                for task in request.definition.tasks
            ],
            message="Fake crew runtime completed deterministically.",
        )


class FakeCrewRuntimeFactory:
    def __init__(self, runtimes: Mapping[str, FakeCrewRuntime] | None = None) -> None:
        self._runtimes = dict(runtimes or {})
        self.created_for: list[str] = []

    def create(self, crew_id: str) -> FakeCrewRuntime:
        self.created_for.append(crew_id)
        runtime = self._runtimes.get(crew_id)
        if runtime is not None:
            return runtime
        runtime = FakeCrewRuntime()
        self._runtimes[crew_id] = runtime
        return runtime


class DisabledCrewRuntime:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = (
            reason or "Crew execution is disabled because CrewAI is not installed or configured."
        )

    def run(self, request: CrewRunRequest) -> CrewRunResult:
        return CrewRunResult(
            crew_id=request.crew_id,
            status=CrewExecutionStatus.FAILED,
            task_results=[],
            message=self.reason,
        )


class DisabledCrewRuntimeFactory:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    def create(self, crew_id: str) -> DisabledCrewRuntime:
        return DisabledCrewRuntime(self.reason)
