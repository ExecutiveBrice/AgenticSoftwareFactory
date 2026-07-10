from pathlib import Path

from ai_software_factory.crews.base import BaseCrew
from ai_software_factory.crews.runtime import CrewRunResult, CrewRuntime, CrewRuntimeFactory
from ai_software_factory.models import CrewExecutionStatus, QAVerdict, ReviewReport


class ReviewCrew(BaseCrew):
    crew_id = "review"

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
        self._request_id = "REVIEW"

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        prepared = super()._prepare_inputs(inputs)
        self._request_id = prepared.get("request_id", "REVIEW")
        verdict = prepared.get("qa_verdict", "")
        if verdict in {QAVerdict.FAILED.value, QAVerdict.BLOCKED.value}:
            raise ValueError("Review refuses QA FAILED or BLOCKED results.")
        prepared.setdefault("follow_up_policy", "proposals_not_approved_tasks")
        return prepared

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is not CrewExecutionStatus.COMPLETED:
            return None
        payload = next(
            (
                task.pydantic_output
                for task in run_result.task_results
                if task.task_id == "issue_final_review" and task.pydantic_output
            ),
            None,
        )
        if payload is None:
            return "Review requires a structured verdict report."
        ReviewReport.model_validate(payload)
        return None

    def _artifact_inputs(self) -> dict[str, str]:
        return {"request_id": self._request_id}
