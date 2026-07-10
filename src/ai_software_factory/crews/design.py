from pathlib import Path

from ai_software_factory.crews.base import BaseCrew
from ai_software_factory.crews.runtime import CrewRunResult, CrewRuntime, CrewRuntimeFactory
from ai_software_factory.models import CrewExecutionStatus


class DesignCrew(BaseCrew):
    crew_id = "design"

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
        self._request_id = "DESIGN"

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        prepared = super()._prepare_inputs(inputs)
        self._request_id = prepared.get("request_id", "DESIGN")
        approved = prepared.get("specification_approved", "false").lower() == "true"
        if not approved:
            raise ValueError("Design requires an approved specification.")
        prepared.setdefault("enable_ux", "false")
        prepared.setdefault("enable_domain", "false")
        prepared.setdefault("enable_security", "false")
        return prepared

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is CrewExecutionStatus.COMPLETED and not run_result.task_results:
            return "Design runtime must execute tasks before returning a completed result."
        return None

    def _artifact_inputs(self) -> dict[str, str]:
        return {"request_id": self._request_id}
