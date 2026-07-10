from pathlib import Path

from ai_software_factory.crews.base import BaseCrew
from ai_software_factory.crews.runtime import CrewRunResult, CrewRuntime, CrewRuntimeFactory
from ai_software_factory.models import CrewExecutionStatus, PlanningGraph


class PlanningCrew(BaseCrew):
    crew_id = "planning"

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
        self._request_id = "PLANNING"

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        prepared = super()._prepare_inputs(inputs)
        self._request_id = prepared.get("request_id", "PLANNING")
        if prepared.get("design_approved", "false").lower() != "true":
            raise ValueError("Planning requires an approved design.")
        prepared.setdefault("task_sizing", "small_verifiable_tasks")
        return prepared

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is not CrewExecutionStatus.COMPLETED:
            return None
        graph_payload = next(
            (
                task.pydantic_output
                for task in run_result.task_results
                if task.task_id == "validate_task_graph" and task.pydantic_output
            ),
            None,
        )
        if graph_payload is None:
            return None
        graph = PlanningGraph.model_validate(graph_payload)
        task_ids = {task.id for task in graph.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> bool:
            if task_id in visiting:
                return False
            if task_id in visited:
                return True
            visiting.add(task_id)
            task = next(item for item in graph.tasks if item.id == task_id)
            for dependency in task.depends_on:
                if dependency not in task_ids or not visit(dependency):
                    return False
            visiting.remove(task_id)
            visited.add(task_id)
            return True

        if not all(visit(task.id) for task in graph.tasks):
            return "Planning graph must be acyclic and reference existing tasks."
        return None

    def _artifact_inputs(self) -> dict[str, str]:
        return {"request_id": self._request_id}
