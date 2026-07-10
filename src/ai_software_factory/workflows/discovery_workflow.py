from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_software_factory.crews.discovery import DiscoveryCrew
from ai_software_factory.crews.runtime import CrewRuntime
from ai_software_factory.flows.persistence import StateStore
from ai_software_factory.models import (
    CrewExecutionStatus,
    DiscoveryQuestions,
    DiscoveryVerdict,
    WorkflowState,
    WorkflowStatus,
)
from ai_software_factory.services.artifact_service import ArtifactService
from ai_software_factory.services.identifier_service import IdentifierService
from ai_software_factory.services.repository_policy import policy_for_crew
from ai_software_factory.tools.read_only import RepositoryReadOnlyTools


@dataclass(frozen=True)
class DiscoveryRunResult:
    state: WorkflowState
    artifacts: tuple[str, ...]


class DiscoveryWorkflow:
    def __init__(self, repository_path: Path, *, runtime: CrewRuntime | None = None) -> None:
        self.repository_path = repository_path.resolve()
        self.runtime = runtime
        self.ids = IdentifierService(self.repository_path)
        self.store = StateStore(self.repository_path)
        self.artifacts = ArtifactService(self.repository_path, policy=policy_for_crew("discovery"))
        self.tools = RepositoryReadOnlyTools(self.repository_path)

    def start(self, raw_request: str) -> DiscoveryRunResult:
        request_id = self.ids.request_id()
        feature_id = self.ids.feature_id()
        state = WorkflowState(
            request_id=request_id,
            feature_id=feature_id,
            repository_path=self.repository_path,
            current_stage=WorkflowStatus.DISCOVERY_RUNNING,
            status=WorkflowStatus.DISCOVERY_RUNNING,
            transition_history=[f"NEW->DISCOVERY_RUNNING: {raw_request}"],
        )
        inputs = self._collect_inputs(raw_request, request_id, feature_id)
        crew = DiscoveryCrew(self.repository_path, runtime=self.runtime)
        crew_result = crew.kickoff(**inputs)
        if crew_result.status == CrewExecutionStatus.FAILED:
            state.status = WorkflowStatus.FAILED
            state.current_stage = WorkflowStatus.FAILED
            state.transition_history.append(f"DISCOVERY_RUNNING->FAILED: {crew_result.message}")
            self.store.save(state)
            return DiscoveryRunResult(state, ())
        questions = self._questions_from_runtime(crew.last_run_result)
        written = self._write_analysis_artifacts(request_id, raw_request, inputs, questions)
        blocking = [q.question for q in questions.questions if q.blocking]
        if blocking and not questions.can_continue_without_human:
            state.pending_questions = blocking
            state.status = WorkflowStatus.WAITING_FOR_CLARIFICATION
            state.current_stage = WorkflowStatus.WAITING_FOR_CLARIFICATION
            state.transition_history.append("DISCOVERY_RUNNING->WAITING_FOR_CLARIFICATION")
            self.store.save(state)
            return DiscoveryRunResult(state, tuple(written))
        spec_artifacts = self._write_specification_artifacts(
            request_id, feature_id, raw_request, inputs
        )
        written.extend(spec_artifacts)
        state.specification_path = Path(f"project/specifications/{feature_id}.md")
        state.status = WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
        state.current_stage = WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
        state.transition_history.append("DISCOVERY_RUNNING->WAITING_FOR_SPEC_APPROVAL")
        self.store.save(state)
        return DiscoveryRunResult(state, tuple(written))

    def resume_with_answers(self, request_id: str, answers: str) -> DiscoveryRunResult:
        state = self.store.load(request_id)
        if state.status != WorkflowStatus.WAITING_FOR_CLARIFICATION:
            raise ValueError(
                "Discovery can resume with answers only while waiting for clarification"
            )
        if state.feature_id is None:
            raise ValueError("Discovery state has no feature id")
        state.pending_questions = []
        written = self._write_specification_artifacts(
            request_id, state.feature_id, f"Human answers:\n{answers}", {"human_answers": answers}
        )
        state.specification_path = Path(f"project/specifications/{state.feature_id}.md")
        state.status = WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
        state.current_stage = WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
        state.transition_history.append("WAITING_FOR_CLARIFICATION->WAITING_FOR_SPEC_APPROVAL")
        self.store.save(state)
        return DiscoveryRunResult(state, tuple(written))

    def record_product_owner_decision(
        self,
        request_id: str,
        verdict: DiscoveryVerdict,
        *,
        required_changes: tuple[str, ...] = (),
    ) -> WorkflowState:
        state = self.store.load(request_id)
        if state.status != WorkflowStatus.WAITING_FOR_SPEC_APPROVAL:
            raise ValueError("Product Owner decision requires a specification awaiting approval")
        if verdict is DiscoveryVerdict.APPROVED:
            state.status = WorkflowStatus.COMPLETED
        elif verdict is DiscoveryVerdict.CHANGES_REQUESTED:
            state.status = WorkflowStatus.WAITING_FOR_CLARIFICATION
            state.pending_questions = list(required_changes)
        else:
            state.status = WorkflowStatus.REJECTED
        state.current_stage = state.status
        state.transition_history.append(f"WAITING_FOR_SPEC_APPROVAL->{state.status}: {verdict}")
        self.store.save(state)
        return state

    def _collect_inputs(self, raw_request: str, request_id: str, feature_id: str) -> dict[str, str]:
        files = self.tools.list_files()
        focus = [".factory.yaml", "project/context.md"]
        docs = [p for p in files if p.startswith("docs/") or p.startswith("project/")]
        code = [p for p in files if p in {"README.md", "pyproject.toml"} or p.startswith("src/")]
        return {
            "repository_path": str(self.repository_path),
            "raw_request": raw_request,
            "request_id": request_id,
            "feature_id": feature_id,
            "file_list": "\n".join(files),
            "required_files": "\n\n".join(
                f"# {p}\n{self.tools.read_text(p)}"
                for p in focus
                if (self.repository_path / p).is_file()
            ),
            "documentation_files": "\n".join(docs),
            "structuring_files": "\n".join(code[:80]),
            "git_metadata": self.tools.git_metadata(),
            "dependency_summary": self.tools.dependency_summary(),
        }

    def _questions_from_runtime(self, run_result: object) -> DiscoveryQuestions:
        if run_result is None:
            return DiscoveryQuestions(questions=[], can_continue_without_human=True)
        task_results = getattr(run_result, "task_results", [])
        for task_result in task_results:
            if getattr(task_result, "task_id", "") == "identify_open_questions":
                payload = getattr(task_result, "pydantic_output", None)
                if payload is not None:
                    return DiscoveryQuestions.model_validate(payload)
        return DiscoveryQuestions(questions=[], can_continue_without_human=True)

    def _write_analysis_artifacts(
        self,
        request_id: str,
        raw_request: str,
        inputs: dict[str, str],
        questions: DiscoveryQuestions,
    ) -> list[str]:
        base = f"project/discovery/{request_id}"
        repo = "\n".join(
            [
                "# Repository analysis",
                "",
                "## Inputs",
                f"- Request: {raw_request}",
                f"- Repository: {inputs['repository_path']}",
                "",
                "## Files considered",
                inputs["file_list"],
                "",
                "## Git metadata",
                inputs["git_metadata"],
                "",
                "## Dependencies",
                inputs["dependency_summary"],
                "",
            ]
        )
        req = "\n".join(
            [
                "# Request analysis",
                "",
                "## Request",
                raw_request,
                "",
                "## Traceability",
                f"- request_id: {request_id}",
                "",
                "## Ambiguities",
                "Derived from Discovery task outputs and human answers when present.",
                "",
            ]
        )
        openq = "# Open questions\n\n" + (
            "No blocking questions identified.\n"
            if not questions.questions
            else "\n".join(f"- {q.id}: {q.question}" for q in questions.questions)
        )
        paths = [
            (f"{base}/repository-analysis.md", repo),
            (f"{base}/request-analysis.md", req),
            (f"{base}/open-questions.md", openq),
        ]
        for path, content in paths:
            self.artifacts.write_text(path, content, overwrite=True)
        return [p for p, _ in paths]

    def _write_specification_artifacts(
        self,
        request_id: str,
        feature_id: str,
        raw_request: str,
        inputs: dict[str, str],
    ) -> list[str]:
        spec_path = f"project/specifications/{feature_id}.md"
        validation_path = f"project/discovery/{request_id}/product-owner-validation.md"
        spec = "\n".join(
            [
                f"# Specification {feature_id}",
                "",
                "## Overview",
                raw_request,
                "",
                "## Requirements",
                "- Satisfy the validated request while preserving existing tested behavior.",
                "",
                "## Acceptance Criteria",
                f"- Discovery artifacts are traceable to `{request_id}`.",
                "- Changes remain limited to authorized Discovery outputs.",
                "",
                "## Non-goals",
                "- No downstream crew is started by this workflow.",
                "",
                "## Risks",
                "- Human approval is required before downstream work.",
                "",
                "## Traceability",
                f"- request_id: {request_id}",
                f"- feature_id: {feature_id}",
                "- inputs: repository_path, raw_request, repository files",
                "- inputs: git metadata, dependencies",
                "",
            ]
        )
        validation = "\n".join(
            [
                "# Product Owner validation",
                "",
                f"Specification ready for approval: `{spec_path}`.",
                "",
                "Options: APPROVED, CHANGES_REQUESTED, REJECTED.",
                "",
            ]
        )
        self.artifacts.write_text(spec_path, spec, overwrite=True)
        self.artifacts.write_text(validation_path, validation, overwrite=True)
        return [spec_path, validation_path]
