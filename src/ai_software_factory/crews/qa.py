from pathlib import Path

from ai_software_factory.crews.base import BaseCrew
from ai_software_factory.crews.runtime import CrewRunResult, CrewRuntime, CrewRuntimeFactory
from ai_software_factory.models import CrewExecutionStatus, QAReport


class QaCrew(BaseCrew):
    crew_id = "qa"

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
        prepared.setdefault("code_access", "read_only")
        return prepared

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is not CrewExecutionStatus.COMPLETED:
            return None
        payload = next(
            (
                task.pydantic_output
                for task in run_result.task_results
                if task.task_id == "write_qa_report" and task.pydantic_output
            ),
            None,
        )
        if payload is None:
            return "QA requires a structured verdict report."
        report = QAReport.model_validate(payload)
        if not report.acceptance_matrix:
            return "QA report requires a criterion/test/evidence matrix."
        return None

    def _artifact_inputs(self) -> dict[str, str]:
        return {"task_id": self._task_id}
