from pathlib import Path

from ai_software_factory.crews.runtime import (
    CrewRunRequest,
    CrewRunResult,
    CrewRuntime,
    CrewRuntimeFactory,
    DisabledCrewRuntimeFactory,
)
from ai_software_factory.crews.shared.validation import load_crew_definition
from ai_software_factory.models import CrewDefinition, CrewExecutionResult, CrewExecutionStatus
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
        if run_result.crew_id != self.crew_id:
            return CrewExecutionResult(
                crew_id=self.crew_id,
                status=CrewExecutionStatus.FAILED,
                message=(
                    f"Crew runtime returned result for '{run_result.crew_id}' instead of "
                    f"'{self.crew_id}'."
                ),
            )
        return CrewExecutionResult(
            crew_id=run_result.crew_id,
            status=run_result.status,
            message=run_result.message,
        )

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        return dict(sorted(inputs.items()))
