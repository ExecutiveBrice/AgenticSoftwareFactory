from pathlib import Path

from ai_software_factory.crews.runtime import (
    CrewRunRequest,
    CrewRunResult,
    CrewRuntime,
    CrewRuntimeFactory,
    DisabledCrewRuntimeFactory,
)
from ai_software_factory.crews.shared.validation import load_crew_definition
from ai_software_factory.models import (
    ArtifactReference,
    CrewDefinition,
    CrewExecutionResult,
    CrewExecutionStatus,
)
from ai_software_factory.services import ArtifactService, policy_for_crew


class BaseCrew:
    crew_id: str

    def __init__(
        self,
        repository_path: Path,
        *,
        task_paths: tuple[str | Path, ...] = (),
        runtime: CrewRuntime | None = None,
        runtime_factory: CrewRuntimeFactory | None = None,
    ) -> None:
        self.repository_path = repository_path
        self.policy = policy_for_crew(self.crew_id, task_paths=task_paths)
        self.artifacts = ArtifactService(repository_path, policy=self.policy)
        self._runtime = runtime
        self._runtime_factory = runtime_factory or DisabledCrewRuntimeFactory()
        self.last_run_result: CrewRunResult | None = None

    def build(self) -> CrewDefinition:
        return load_crew_definition(self.crew_id)

    def kickoff(self, **kwargs: str) -> CrewExecutionResult:
        definition = self.build()
        inputs = self._prepare_inputs(kwargs)
        runtime = self._runtime or self._runtime_factory.create(self.crew_id)
        raw_result = runtime.run(
            CrewRunRequest(
                crew_id=self.crew_id,
                repository_path=self.repository_path,
                definition=definition,
                inputs=inputs,
            )
        )
        run_result = (
            raw_result
            if isinstance(raw_result, CrewRunResult)
            else CrewRunResult.model_validate(raw_result)
        )
        self.last_run_result = run_result
        if run_result.crew_id != self.crew_id:
            return CrewExecutionResult(
                crew_id=self.crew_id,
                status=CrewExecutionStatus.FAILED,
                message=(
                    f"Crew runtime returned result for '{run_result.crew_id}' instead of "
                    f"'{self.crew_id}'."
                ),
            )
        validation_error = self._validate_run_result(run_result)
        if validation_error is not None:
            return CrewExecutionResult(
                crew_id=self.crew_id,
                status=CrewExecutionStatus.FAILED,
                message=validation_error,
            )
        artifacts = self._write_task_artifacts(definition, run_result)
        return CrewExecutionResult(
            crew_id=run_result.crew_id,
            status=run_result.status,
            artifacts=artifacts,
            message=run_result.message,
        )

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        return dict(sorted(inputs.items()))

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is not CrewExecutionStatus.COMPLETED:
            return None
        return None

    def _write_task_artifacts(
        self, definition: CrewDefinition, run_result: CrewRunResult
    ) -> list[ArtifactReference]:
        outputs = {task.task_id: task.output for task in run_result.task_results}
        artifacts: list[ArtifactReference] = []
        for task in definition.tasks:
            if task.output_file is None:
                continue
            path = task.output_file.format_map(_DefaultInputs(self._artifact_inputs()))
            content = outputs.get(task.id) or run_result.final_output or run_result.message
            artifacts.append(self.artifacts.write_text(path, content, overwrite=True))
        return artifacts

    def _artifact_inputs(self) -> dict[str, str]:
        return {}


class _DefaultInputs(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return key
