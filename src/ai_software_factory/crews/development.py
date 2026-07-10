from pathlib import Path

from ai_software_factory.crews.base import BaseCrew
from ai_software_factory.crews.runtime import CrewRunResult, CrewRuntime, CrewRuntimeFactory
from ai_software_factory.models import CrewExecutionStatus, DevelopmentManifest

_DESTRUCTIVE_COMMANDS = ("rm -rf", "git reset --hard", "git clean", "mkfs", ":(){")


class DevelopmentCrew(BaseCrew):
    crew_id = "development"

    def __init__(
        self,
        repository_path: Path,
        *,
        task_paths: tuple[str | Path, ...] = (),
        runtime: CrewRuntime | None = None,
        runtime_factory: CrewRuntimeFactory | None = None,
    ) -> None:
        super().__init__(
            repository_path,
            task_paths=task_paths,
            runtime=runtime,
            runtime_factory=runtime_factory,
        )
        self._task_id = "TASK"

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        prepared = super()._prepare_inputs(inputs)
        self._task_id = prepared.get("task_id", "TASK")
        if prepared.get("single_task", "true").lower() != "true":
            raise ValueError("Development executes exactly one task at a time.")
        command = prepared.get("command", "")
        if any(blocked in command.lower() for blocked in _DESTRUCTIVE_COMMANDS):
            raise ValueError("Development refuses destructive implicit commands.")
        prepared.setdefault("command_runner", "safe_explicit_commands_only")
        return prepared

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is not CrewExecutionStatus.COMPLETED:
            return None
        payload = next(
            (
                task.pydantic_output
                for task in run_result.task_results
                if task.task_id == "prepare_implementation_manifest" and task.pydantic_output
            ),
            None,
        )
        if payload is None:
            return "Development requires a structured implementation manifest."
        DevelopmentManifest.model_validate(payload)
        return None

    def _artifact_inputs(self) -> dict[str, str]:
        return {"task_id": self._task_id}
