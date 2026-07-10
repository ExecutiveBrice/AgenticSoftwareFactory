from ai_software_factory.crews.base import BaseCrew
from ai_software_factory.crews.runtime import CrewRunResult
from ai_software_factory.models import CrewExecutionStatus


class KnowledgeCrew(BaseCrew):
    crew_id = "knowledge"

    def _prepare_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        prepared = super()._prepare_inputs(inputs)
        prepared.setdefault("change_mode", "propose_then_apply_controlled_updates")
        prepared.setdefault("decision_boundary", "proposals_are_not_validated_decisions")
        prepared.setdefault(
            "completion_boundary", "features_cannot_be_completed_before_review_acceptance"
        )
        return prepared

    def _validate_run_result(self, run_result: CrewRunResult) -> str | None:
        if run_result.status is not CrewExecutionStatus.COMPLETED:
            return None
        text = "\n".join(
            [run_result.final_output, *(task.output for task in run_result.task_results)]
        ).lower()
        forbidden = ("validated decision", "feature completed", "feature is complete")
        if any(term in text for term in forbidden):
            return (
                "Knowledge output must keep proposals separate from validated decisions "
                "and completion."
            )
        return None

    def _artifact_inputs(self) -> dict[str, str]:
        return {"decision_id": "PROPOSED-DECISION"}
