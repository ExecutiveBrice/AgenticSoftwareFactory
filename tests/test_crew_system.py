from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ai_software_factory.crews import (
    CrewRunRequest,
    CrewRunResult,
    DisabledCrewRuntime,
    FakeCrewRuntime,
    FakeCrewRuntimeFactory,
    TaskRunResult,
)
from ai_software_factory.crews.design import DesignCrew
from ai_software_factory.crews.development import DevelopmentCrew
from ai_software_factory.crews.discovery import DiscoveryCrew
from ai_software_factory.crews.knowledge import KnowledgeCrew
from ai_software_factory.crews.planning import PlanningCrew
from ai_software_factory.crews.qa import QaCrew
from ai_software_factory.crews.registry import CrewRegistry
from ai_software_factory.crews.review import ReviewCrew
from ai_software_factory.crews.shared import validation as crew_validation
from ai_software_factory.crews.shared.constants import CREW_IDS
from ai_software_factory.crews.shared.validation import (
    CrewYamlValidationError,
    load_crew_definition,
)
from ai_software_factory.flows import FactoryFlow
from ai_software_factory.flows.routing import assert_transition, route_qa, route_review
from ai_software_factory.models import (
    AcceptanceMatrixRow,
    AgentDefinition,
    CrewDefinition,
    CrewExecutionStatus,
    DevelopmentManifest,
    DiscoveryQuestion,
    DiscoveryQuestions,
    DiscoveryVerdict,
    PlanningGraph,
    PlanningTask,
    QAReport,
    QAVerdict,
    ReviewReport,
    ReviewVerdict,
    TaskDefinition,
    WorkflowState,
    WorkflowStatus,
)
from ai_software_factory.services import ArtifactService, IdentifierService
from ai_software_factory.tools import RepositoryReadOnlyTools
from ai_software_factory.workflows import DiscoveryWorkflow


def test_models_and_verdicts(tmp_path: Path) -> None:
    WorkflowState(request_id="REQ-0001", repository_path=tmp_path)
    assert DiscoveryVerdict.APPROVED == "APPROVED"
    assert QAVerdict.BLOCKED == "BLOCKED"
    assert ReviewVerdict.APPROVED_WITH_FOLLOW_UP == "APPROVED_WITH_FOLLOW_UP"


def test_artifact_service_security(tmp_path: Path) -> None:
    svc = ArtifactService(tmp_path)
    ref = svc.write_text("project/a.md", "x")
    assert ref.exists
    with pytest.raises(FileExistsError):
        svc.write_text("project/a.md", "y")
    with pytest.raises(ValueError):
        svc.write_text("../outside.md", "x")


def test_identifier_service(tmp_path: Path) -> None:
    (tmp_path / "project").mkdir()
    (tmp_path / "project" / "FEAT-0001-a.md").write_text("")
    ids = IdentifierService(tmp_path)
    assert ids.request_id() == "REQ-0001"
    assert ids.feature_id() == "FEAT-0002"
    assert ids.task_id(1, 1) == "TASK-0001-01"


def test_registry_detects_duplicate() -> None:
    d = CrewDefinition(
        id="x",
        description="x",
        agents=[AgentDefinition(id="a", role="r", goal="g", backstory="b")],
        tasks=[],
    )
    r = CrewRegistry()
    r.register(d)
    with pytest.raises(ValueError):
        r.register(d)


def test_all_yaml_resources_valid() -> None:
    for cid in CREW_IDS:
        d = load_crew_definition(cid)
        assert d.agents and d.tasks
        assert len({a.id for a in d.agents}) == len(d.agents)
        assert all(t.agent in {a.id for a in d.agents} for t in d.tasks)


def test_flow_routing_and_persistence(tmp_path: Path) -> None:
    flow = FactoryFlow(tmp_path)
    s = flow.start_request("add generic feature")
    assert flow.resume(s.request_id).status == "DISCOVERY_RUNNING"
    flow.transition(s, "WAITING_FOR_SPEC_APPROVAL")
    assert route_qa(QAVerdict.FAILED) == "DEVELOPMENT_RUNNING"
    assert route_qa(QAVerdict.BLOCKED) == "WAITING_FOR_PRODUCT_ACCEPTANCE"
    assert route_review(ReviewVerdict.CHANGES_REQUESTED) == "DEVELOPMENT_RUNNING"
    assert route_review(ReviewVerdict.REJECTED) == "DESIGN_RUNNING"
    with pytest.raises(ValueError):
        assert_transition("COMPLETED", "NEW")


@contextmanager
def _crew_yaml_resources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    crew_id: str,
    agents: str | None,
    tasks: str | None,
) -> Iterator[None]:
    crew_dir = tmp_path / crew_id
    crew_dir.mkdir(parents=True)
    if agents is not None:
        (crew_dir / "agents.yaml").write_text(agents, encoding="utf-8")
    if tasks is not None:
        (crew_dir / "tasks.yaml").write_text(tasks, encoding="utf-8")
    monkeypatch.setattr(crew_validation.resources, "files", lambda _package: tmp_path)
    yield


_VALID_AGENTS = """
agents:
  analyst:
    role: Analyst
    goal: Understand generic needs
    backstory: Works generically.
"""

_VALID_TASKS = """
tasks:
  inspect:
    description: Inspect generic inputs.
    expected_output: A generic report.
    agent: analyst
    context: []
"""


def test_yaml_loader_accepts_valid_yaml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    with _crew_yaml_resources(monkeypatch, tmp_path, "valid", _VALID_AGENTS, _VALID_TASKS):
        definition = load_crew_definition("valid")

    assert definition.agents[0].id == "analyst"
    assert definition.tasks[0].context == []


def test_yaml_loader_accepts_multiline_lists_booleans_and_output_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tasks = """
tasks:
  inspect:
    description: |
      Inspect generic inputs.
      Preserve multiline text.
    expected_output: >
      A generic report
      with folded text.
    agent: analyst
    context: []
    output_path: project/reports/generic.md
    optional: true
  summarize:
    description: Summarize generic findings.
    expected_output: Summary.
    agent: analyst
    context:
      - inspect
"""
    with _crew_yaml_resources(monkeypatch, tmp_path, "multiline", _VALID_AGENTS, tasks):
        definition = load_crew_definition("multiline")

    assert "Preserve multiline text" in definition.tasks[0].description
    assert definition.tasks[0].optional is True
    assert definition.tasks[0].output_path == "project/reports/generic.md"
    assert definition.tasks[1].context == ["inspect"]


def test_yaml_loader_rejects_empty_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _crew_yaml_resources(monkeypatch, tmp_path, "empty", "", _VALID_TASKS):
        with pytest.raises(CrewYamlValidationError, match="document must not be empty"):
            load_crew_definition("empty")


def test_yaml_loader_rejects_unexpected_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agents = """
unknown:
  analyst:
    role: Analyst
"""
    with _crew_yaml_resources(monkeypatch, tmp_path, "bad-root", agents, _VALID_TASKS):
        with pytest.raises(CrewYamlValidationError, match="no unexpected keys"):
            load_crew_definition("bad-root")


def test_yaml_loader_rejects_invalid_yaml_syntax(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _crew_yaml_resources(monkeypatch, tmp_path, "invalid", "agents: [", _VALID_TASKS):
        with pytest.raises(CrewYamlValidationError, match="invalid YAML syntax"):
            load_crew_definition("invalid")


def test_yaml_loader_rejects_agent_missing_required_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agents = """
agents:
  analyst:
    role: Analyst
    backstory: Works generically.
"""
    with _crew_yaml_resources(monkeypatch, tmp_path, "missing-agent", agents, _VALID_TASKS):
        with pytest.raises(CrewYamlValidationError, match="agents.analyst.goal"):
            load_crew_definition("missing-agent")


def test_yaml_loader_rejects_task_missing_required_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tasks = """
tasks:
  inspect:
    description: Inspect generic inputs.
    agent: analyst
    context: []
"""
    with _crew_yaml_resources(monkeypatch, tmp_path, "missing-task", _VALID_AGENTS, tasks):
        with pytest.raises(CrewYamlValidationError, match="tasks.inspect.expected_output"):
            load_crew_definition("missing-task")


def test_yaml_loader_rejects_task_with_unknown_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tasks = _VALID_TASKS.replace("agent: analyst", "agent: unknown")
    with _crew_yaml_resources(monkeypatch, tmp_path, "unknown-agent", _VALID_AGENTS, tasks):
        with pytest.raises(CrewYamlValidationError, match="unknown agent 'unknown'"):
            load_crew_definition("unknown-agent")


def test_yaml_loader_rejects_unknown_context_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tasks = _VALID_TASKS.replace("context: []", "context:\n      - missing")
    with _crew_yaml_resources(monkeypatch, tmp_path, "unknown-context", _VALID_AGENTS, tasks):
        with pytest.raises(CrewYamlValidationError, match="unknown task 'missing'"):
            load_crew_definition("unknown-context")


def test_yaml_loader_rejects_cyclic_context_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tasks = """
tasks:
  first:
    description: First generic task.
    expected_output: First output.
    agent: analyst
    context:
      - second
  second:
    description: Second generic task.
    expected_output: Second output.
    agent: analyst
    context:
      - first
"""
    with _crew_yaml_resources(monkeypatch, tmp_path, "cycle", _VALID_AGENTS, tasks):
        with pytest.raises(CrewYamlValidationError, match="context graph contains a cycle"):
            load_crew_definition("cycle")


def test_yaml_loader_rejects_missing_resource(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with _crew_yaml_resources(monkeypatch, tmp_path, "missing-resource", _VALID_AGENTS, None):
        with pytest.raises(CrewYamlValidationError, match="required YAML resource is missing"):
            load_crew_definition("missing-resource")


def test_yaml_resources_are_accessible_from_installed_package() -> None:
    import importlib.resources

    for crew_id in CREW_IDS:
        base = importlib.resources.files("ai_software_factory.resources.crews").joinpath(crew_id)
        assert base.joinpath("agents.yaml").is_file()
        assert base.joinpath("tasks.yaml").is_file()


_STRUCTURED_OUTPUT_MODELS = {
    "DevelopmentManifest",
    "DiscoveryQuestions",
    "ProductOwnerDecision",
    "QAReport",
    "ReviewReport",
}


def test_executable_task_resources_are_specific_and_routable() -> None:
    for cid in CREW_IDS:
        definition = load_crew_definition(cid)
        task_ids = {task.id for task in definition.tasks}
        agent_ids = {agent.id for agent in definition.agents}
        assert len(task_ids) == len(definition.tasks)
        for index, task in enumerate(definition.tasks):
            assert task.agent in agent_ids
            assert "Execute " not in task.description
            assert "Validated markdown or YAML artifact" not in task.expected_output
            assert len(task.description) >= 300
            assert len(task.expected_output) >= 80
            assert task.markdown is True
            assert task.context or index == 0 or cid == "review"
            assert task.output_file or task.human_input
            if task.output_model is not None:
                assert task.output_model in _STRUCTURED_OUTPUT_MODELS
        assert task_ids == {task.id for task in definition.tasks}


def test_required_task_context_graphs_are_declared() -> None:
    expected_contexts = {
        "discovery": {
            "inspect_project": [],
            "analyse_request": ["inspect_project"],
            "identify_open_questions": ["inspect_project", "analyse_request"],
            "prepare_human_clarification": ["identify_open_questions"],
            "write_feature_specification": [
                "inspect_project",
                "analyse_request",
                "identify_open_questions",
            ],
            "prepare_product_owner_validation": ["write_feature_specification"],
        },
        "knowledge": {
            "collect_project_changes": [],
            "update_project_context": ["collect_project_changes"],
            "update_glossary": ["collect_project_changes"],
            "update_roadmap": ["collect_project_changes"],
            "record_decisions": ["collect_project_changes"],
            "update_changelog": ["collect_project_changes"],
            "audit_project_knowledge": [
                "collect_project_changes",
                "update_project_context",
                "update_glossary",
                "update_roadmap",
                "record_decisions",
                "update_changelog",
            ],
        },
        "design": {
            "analyse_design_context": [],
            "design_domain_changes": ["analyse_design_context"],
            "design_user_experience": ["analyse_design_context"],
            "assess_security_and_privacy": ["analyse_design_context"],
            "design_technical_solution": [
                "design_domain_changes",
                "design_user_experience",
                "assess_security_and_privacy",
            ],
            "propose_architecture_decisions": ["design_technical_solution"],
            "review_design": [
                "design_domain_changes",
                "design_user_experience",
                "assess_security_and_privacy",
                "design_technical_solution",
                "propose_architecture_decisions",
            ],
            "prepare_design_validation": ["review_design"],
        },
        "planning": {
            "create_feature_delivery_plan": [],
            "create_epic": ["create_feature_delivery_plan"],
            "create_implementation_tasks": ["create_epic", "create_feature_delivery_plan"],
            "create_test_plan": ["create_implementation_tasks"],
            "validate_task_graph": ["create_implementation_tasks", "create_test_plan"],
            "prepare_backlog_validation": ["validate_task_graph"],
        },
        "development": {
            "inspect_task_context": [],
            "prepare_implementation_plan": ["inspect_task_context"],
            "implement_task": ["prepare_implementation_plan"],
            "implement_tests": ["implement_task"],
            "update_local_documentation": ["implement_task", "implement_tests"],
            "run_development_checks": [
                "implement_task",
                "implement_tests",
                "update_local_documentation",
            ],
            "self_review_implementation": ["run_development_checks"],
            "prepare_implementation_manifest": ["self_review_implementation"],
        },
        "qa": {
            "review_acceptance_criteria": [],
            "build_acceptance_matrix": ["review_acceptance_criteria"],
            "execute_targeted_tests": ["build_acceptance_matrix"],
            "execute_regression_tests": ["execute_targeted_tests"],
            "verify_non_functional_requirements": [
                "execute_targeted_tests",
                "execute_regression_tests",
            ],
            "analyse_test_results": [
                "execute_targeted_tests",
                "execute_regression_tests",
                "verify_non_functional_requirements",
            ],
            "write_qa_report": ["analyse_test_results"],
        },
        "review": {
            "review_code_quality": [],
            "review_architecture_compliance": [],
            "review_security": [],
            "review_delivery_readiness": [],
            "consolidate_review_findings": [
                "review_code_quality",
                "review_architecture_compliance",
                "review_security",
                "review_delivery_readiness",
            ],
            "issue_final_review": ["consolidate_review_findings"],
        },
    }
    for crew_id, contexts in expected_contexts.items():
        tasks = {task.id: task for task in load_crew_definition(crew_id).tasks}
        assert set(tasks) == set(contexts)
        for task_id, context in contexts.items():
            assert tasks[task_id].context == context


def test_human_and_structured_tasks_are_explicit() -> None:
    human_tasks = set()
    structured_tasks = {}
    for cid in CREW_IDS:
        for task in load_crew_definition(cid).tasks:
            if task.human_input:
                human_tasks.add(f"{cid}.{task.id}")
            if task.output_model:
                structured_tasks[f"{cid}.{task.id}"] = task.output_model
    assert human_tasks == {
        "discovery.prepare_human_clarification",
        "discovery.prepare_product_owner_validation",
        "design.prepare_design_validation",
        "planning.prepare_backlog_validation",
    }
    assert structured_tasks == {
        "discovery.identify_open_questions": "DiscoveryQuestions",
        "discovery.prepare_product_owner_validation": "ProductOwnerDecision",
        "development.prepare_implementation_manifest": "DevelopmentManifest",
        "qa.write_qa_report": "QAReport",
        "review.issue_final_review": "ReviewReport",
    }


@pytest.mark.parametrize(
    ("crew_id", "allowed_path"),
    [
        ("discovery", "project/discovery/report.md"),
        ("discovery", "project/specifications/spec.md"),
        ("knowledge", "project/context.md"),
        ("knowledge", "project/decisions/ADR-0001.md"),
        ("design", "project/architecture/FEAT-0001/design.md"),
        ("planning", "project/backlog/FEAT-0001/task.md"),
        ("qa", "project/reviews/QA/report.md"),
        ("review", "project/reviews/TECH/report.md"),
    ],
)
def test_each_crew_writes_inside_its_zone(tmp_path: Path, crew_id: str, allowed_path: str) -> None:
    from ai_software_factory.services import policy_for_crew

    svc = ArtifactService(tmp_path, policy=policy_for_crew(crew_id))

    ref = svc.write_text(allowed_path, "content")

    assert ref.exists


@pytest.mark.parametrize(
    ("crew_id", "forbidden_path"),
    [
        ("discovery", "src/package/code.py"),
        ("knowledge", "project/specifications/spec.md"),
        ("design", "project/architecture-not-really/design.md"),
        ("planning", "project/backlog-old/task.md"),
        ("qa", "project/reviews/TECH/report.md"),
        ("review", "project/reviews/QA/report.md"),
    ],
)
def test_each_crew_is_denied_outside_its_zone(
    tmp_path: Path, crew_id: str, forbidden_path: str
) -> None:
    from ai_software_factory.services import policy_for_crew

    svc = ArtifactService(tmp_path, policy=policy_for_crew(crew_id))

    with pytest.raises(PermissionError):
        svc.write_text(forbidden_path, "content")


def test_permission_policy_blocks_path_traversal_and_absolute_paths(tmp_path: Path) -> None:
    from ai_software_factory.services import policy_for_crew

    svc = ArtifactService(tmp_path, policy=policy_for_crew("discovery"))

    with pytest.raises(ValueError):
        svc.write_text("project/discovery/../../src/code.py", "content")
    with pytest.raises(ValueError):
        svc.write_text(tmp_path / "project" / "discovery" / "absolute.md", "content")


def test_permission_policy_blocks_external_symlink(tmp_path: Path) -> None:
    from ai_software_factory.services import policy_for_crew

    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "project" / "discovery" / "external"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside, target_is_directory=True)
    svc = ArtifactService(tmp_path, policy=policy_for_crew("discovery"))

    with pytest.raises(ValueError):
        svc.write_text("project/discovery/external/report.md", "content")


def test_permission_policy_blocks_unauthorized_delete(tmp_path: Path) -> None:
    from ai_software_factory.services import policy_for_crew

    target = tmp_path / "project" / "reviews" / "QA" / "report.md"
    target.parent.mkdir(parents=True)
    target.write_text("content", encoding="utf-8")
    svc = ArtifactService(tmp_path, policy=policy_for_crew("qa"))

    with pytest.raises(PermissionError):
        svc.delete("project/reviews/QA/report.md")

    assert target.exists()


def test_development_is_limited_to_task_declared_files(tmp_path: Path) -> None:
    from ai_software_factory.services import policy_for_crew

    svc = ArtifactService(
        tmp_path,
        policy=policy_for_crew(
            "development", task_paths=("src/allowed.py", "tests/test_allowed.py")
        ),
    )

    svc.write_text("src/allowed.py", "content")
    svc.write_text("tests/test_allowed.py", "content")
    with pytest.raises(PermissionError):
        svc.write_text("src/not_allowed.py", "content")


def test_human_documents_are_preserved_from_wrong_crews(tmp_path: Path) -> None:
    from ai_software_factory.services import policy_for_crew

    human_doc = tmp_path / "project" / "context.md"
    human_doc.parent.mkdir(parents=True)
    human_doc.write_text("human content", encoding="utf-8")
    svc = ArtifactService(tmp_path, policy=policy_for_crew("design"))

    with pytest.raises(PermissionError):
        svc.write_text("project/context.md", "changed", overwrite=True)

    assert human_doc.read_text(encoding="utf-8") == "human content"


class _InvalidRuntime:
    def run(self, request: CrewRunRequest) -> object:
        return {"crew_id": request.crew_id, "status": "UNKNOWN", "unexpected": True}


def test_fake_runtime_is_deterministic_and_network_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access is forbidden in fake runtime tests")

    monkeypatch.setattr("socket.create_connection", fail_network)
    runtime = FakeCrewRuntime()
    crew = DiscoveryCrew(tmp_path, runtime=runtime)

    result = crew.kickoff(request="generic request")
    second = crew.kickoff(request="generic request")

    assert result.status == CrewExecutionStatus.COMPLETED
    assert result.message == second.message
    assert len(runtime.requests) == 2
    assert runtime.requests[0].inputs == {"request": "generic request"}


def test_disabled_runtime_returns_clear_error(tmp_path: Path) -> None:
    result = DiscoveryCrew(tmp_path, runtime=DisabledCrewRuntime()).kickoff()

    assert result.status == CrewExecutionStatus.FAILED
    assert "CrewAI is not installed or configured" in result.message


def test_runtime_error_result_is_propagated(tmp_path: Path) -> None:
    runtime = FakeCrewRuntime(
        result=CrewRunResult(
            crew_id="discovery",
            status=CrewExecutionStatus.FAILED,
            message="runtime failed clearly",
        )
    )

    result = DiscoveryCrew(tmp_path, runtime=runtime).kickoff()

    assert result.status == CrewExecutionStatus.FAILED
    assert result.message == "runtime failed clearly"


def test_invalid_runtime_result_is_rejected(tmp_path: Path) -> None:
    with pytest.raises((TypeError, ValueError)):
        DiscoveryCrew(tmp_path, runtime=_InvalidRuntime()).kickoff()


def test_valid_runtime_result_is_returned(tmp_path: Path) -> None:
    runtime = FakeCrewRuntime(
        result=CrewRunResult(
            crew_id="discovery",
            status=CrewExecutionStatus.COMPLETED,
            message="valid result",
        )
    )

    result = DiscoveryCrew(tmp_path, runtime=runtime).kickoff(topic="generic")

    assert result.crew_id == "discovery"
    assert result.status == CrewExecutionStatus.COMPLETED
    assert result.message == "valid result"


def test_runtime_factory_injection(tmp_path: Path) -> None:
    runtime = FakeCrewRuntime()
    factory = FakeCrewRuntimeFactory({"discovery": runtime})

    result = DiscoveryCrew(tmp_path, runtime_factory=factory).kickoff()

    assert result.status == CrewExecutionStatus.COMPLETED
    assert factory.created_for == ["discovery"]
    assert runtime.requests[0].crew_id == "discovery"


def test_default_kickoff_no_longer_returns_immediate_completed(tmp_path: Path) -> None:
    result = DiscoveryCrew(tmp_path).kickoff()

    assert result.status == CrewExecutionStatus.FAILED
    assert "CrewAI is not installed or configured" in result.message


def test_normal_package_import_does_not_import_crewai() -> None:
    import sys

    sys.modules.pop("crewai", None)
    __import__("ai_software_factory")
    __import__("ai_software_factory.crews")

    assert "crewai" not in sys.modules


class _FakeAgent:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class _FakeTask:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.output = f"task:{kwargs['description']}"


class _FakeProcess:
    sequential = "sequential"


class _FakeCrewOutput:
    raw = "final raw output"
    usage_metrics = {"total_tokens": 3}

    def __init__(self) -> None:
        self.tasks_output = [
            type("TaskOutput", (), {"name": "first", "raw": "first raw", "pydantic": None})(),
            type(
                "TaskOutput",
                (),
                {
                    "name": "second",
                    "raw": "second raw",
                    "pydantic": DiscoveryQuestions(questions=[], can_continue_without_human=True),
                },
            )(),
        ]


class _FakeCrew:
    created: list["_FakeCrew"] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.kickoff_inputs: dict[str, str] | None = None
        _FakeCrew.created.append(self)

    def kickoff(self, *, inputs: dict[str, str]) -> _FakeCrewOutput:
        self.kickoff_inputs = inputs
        return _FakeCrewOutput()


class _FakeCrewAIModule:
    Agent = _FakeAgent
    Task = _FakeTask
    Crew = _FakeCrew
    Process = _FakeProcess


def _runtime_definition() -> CrewDefinition:
    return CrewDefinition(
        id="runtime",
        description="runtime",
        agents=[AgentDefinition(id="analyst", role="Role", goal="Goal", backstory="Backstory")],
        tasks=[
            TaskDefinition(
                id="first",
                description="First generic task.",
                expected_output="First generic output.",
                agent="analyst",
            ),
            TaskDefinition(
                id="second",
                description="Second generic task.",
                expected_output="Second generic output.",
                agent="analyst",
                context=["first"],
                output_model="DiscoveryQuestions",
            ),
        ],
    )


def test_crewai_runtime_builds_agents_tasks_context_and_sequential_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_software_factory.crews.runtime import CrewAIConfig, CrewAIRuntime

    monkeypatch.setattr(CrewAIRuntime, "_crewai_module", staticmethod(lambda: _FakeCrewAIModule))
    runtime = CrewAIRuntime(CrewAIConfig(llm="configured-llm"))

    crew = runtime.build_crew(_runtime_definition())

    agent = crew.kwargs["agents"][0]
    first, second = crew.kwargs["tasks"]
    assert agent.kwargs["llm"] == "configured-llm"
    assert agent.kwargs["tools"] == []
    assert agent.kwargs["allow_code_execution"] is False
    assert first.kwargs["context"] == []
    assert second.kwargs["context"] == [first]
    assert second.kwargs["output_pydantic"] is DiscoveryQuestions
    assert crew.kwargs["process"] == _FakeProcess.sequential
    assert crew.kwargs["tasks"] == [first, second]


def test_crewai_runtime_runs_kickoff_and_converts_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_software_factory.crews.runtime import CrewAIConfig, CrewAIRuntime, CrewRunRequest

    _FakeCrew.created.clear()
    monkeypatch.setattr(CrewAIRuntime, "_crewai_module", staticmethod(lambda: _FakeCrewAIModule))
    runtime = CrewAIRuntime(CrewAIConfig(llm="configured-llm"))

    result = runtime.run(
        CrewRunRequest(
            crew_id="runtime",
            repository_path=Path.cwd(),
            definition=_runtime_definition(),
            inputs={"request": "generic"},
        )
    )

    assert _FakeCrew.created[-1].kickoff_inputs == {"request": "generic"}
    assert result.status == CrewExecutionStatus.COMPLETED
    assert result.final_output == "final raw output"
    assert [task.task_id for task in result.task_results] == ["first", "second"]
    assert result.task_results[1].pydantic_output == {
        "questions": [],
        "can_continue_without_human": True,
    }
    assert result.usage_metrics == {"total_tokens": 3}


def test_crewai_runtime_requires_llm_configuration() -> None:
    from ai_software_factory.crews.runtime import CrewAIConfigurationError, CrewAIRuntime

    with pytest.raises(CrewAIConfigurationError, match="explicit LLM"):
        CrewAIRuntime()


def test_crewai_runtime_converts_crewai_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_software_factory.crews.runtime import CrewAIConfig, CrewAIRuntime, CrewRunRequest

    class FailingCrew(_FakeCrew):
        def kickoff(self, *, inputs: dict[str, str]) -> _FakeCrewOutput:
            raise RuntimeError("provider unavailable")

    class FailingModule(_FakeCrewAIModule):
        Crew = FailingCrew

    monkeypatch.setattr(CrewAIRuntime, "_crewai_module", staticmethod(lambda: FailingModule))
    runtime = CrewAIRuntime(CrewAIConfig(llm="configured-llm"))

    result = runtime.run(
        CrewRunRequest(
            crew_id="runtime",
            repository_path=Path.cwd(),
            definition=_runtime_definition(),
            inputs={},
        )
    )

    assert result.status == CrewExecutionStatus.FAILED
    assert result.error == "provider unavailable"
    assert "CrewAI execution failed" in result.message


def test_crewai_runtime_rejects_unknown_pydantic_output_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_software_factory.crews.runtime import (
        CrewAIConfig,
        CrewAIConfigurationError,
        CrewAIRuntime,
    )

    monkeypatch.setattr(CrewAIRuntime, "_crewai_module", staticmethod(lambda: _FakeCrewAIModule))
    definition = _runtime_definition()
    definition.tasks[1].output_model = "MissingModel"
    runtime = CrewAIRuntime(CrewAIConfig(llm="configured-llm"))

    with pytest.raises(CrewAIConfigurationError, match="Unknown Pydantic output model"):
        runtime.build_crew(definition)


@pytest.mark.crewai_integration
@pytest.mark.skipif("CREWAI_API_KEY" not in __import__("os").environ, reason="requires API key")
def test_crewai_runtime_optional_integration_requires_external_key() -> None:
    pytest.skip(
        "Optional smoke test placeholder; enable with a real configured LLM "
        "in a secure environment."
    )


def _seed_discovery_repo(path: Path) -> None:
    (path / ".factory.yaml").write_text("project: generic\n", encoding="utf-8")
    (path / "project").mkdir()
    (path / "project" / "context.md").write_text(
        "# Context\nGeneric project context.\n", encoding="utf-8"
    )
    (path / "docs").mkdir()
    (path / "docs" / "architecture.md").write_text(
        "# Architecture\nGeneric architecture.\n", encoding="utf-8"
    )
    (path / "project" / "backlog.md").write_text("# Backlog\n", encoding="utf-8")
    (path / "project" / "specifications").mkdir()
    (path / "project" / "specifications" / "existing.md").write_text(
        "# Existing spec\n", encoding="utf-8"
    )
    (path / "src").mkdir()
    (path / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (path / "pyproject.toml").write_text("[project]\nname='generic'\n", encoding="utf-8")


def _runtime_with_questions(blocking: bool) -> FakeCrewRuntime:
    questions = DiscoveryQuestions(
        questions=[
            DiscoveryQuestion(
                id="Q1",
                question="Which validated outcome should be specified?",
                reason="The request lacks an outcome.",
                impact="Specification would otherwise guess scope.",
                options=["Option A", "Option B"],
                blocking=blocking,
            )
        ],
        can_continue_without_human=not blocking,
    )
    return FakeCrewRuntime(
        result=CrewRunResult(
            crew_id="discovery",
            status=CrewExecutionStatus.COMPLETED,
            task_results=[
                TaskRunResult(
                    task_id="inspect_project", output="representative repository analysis"
                ),
                TaskRunResult(task_id="analyse_request", output="representative request analysis"),
                TaskRunResult(
                    task_id="identify_open_questions",
                    output="representative open questions",
                    pydantic_output=questions.model_dump(),
                ),
            ],
            final_output="representative discovery output",
        )
    )


def test_discovery_workflow_clear_request_generates_spec_and_traceable_inputs(
    tmp_path: Path,
) -> None:
    _seed_discovery_repo(tmp_path)
    runtime = FakeCrewRuntime()

    result = DiscoveryWorkflow(tmp_path, runtime=runtime).start(
        "Add a clearly scoped generic capability"
    )

    assert result.state.status == WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
    assert result.state.request_id == "REQ-0001"
    assert result.state.feature_id == "FEAT-0001"
    assert (tmp_path / "project" / "discovery" / "REQ-0001" / "repository-analysis.md").is_file()
    assert (tmp_path / "project" / "discovery" / "REQ-0001" / "request-analysis.md").is_file()
    assert (tmp_path / "project" / "discovery" / "REQ-0001" / "open-questions.md").is_file()
    spec = tmp_path / "project" / "specifications" / "FEAT-0001.md"
    assert spec.is_file()
    assert "Satisfy the validated request" in spec.read_text(encoding="utf-8")
    assert runtime.requests[0].inputs["repository_path"] == str(tmp_path.resolve())
    assert runtime.requests[0].inputs["raw_request"] == "Add a clearly scoped generic capability"
    assert ".factory.yaml" in runtime.requests[0].inputs["file_list"]
    assert "project/context.md" in runtime.requests[0].inputs["required_files"]


def test_discovery_workflow_ambiguous_request_suspends_without_spec(tmp_path: Path) -> None:
    _seed_discovery_repo(tmp_path)

    result = DiscoveryWorkflow(tmp_path, runtime=_runtime_with_questions(True)).start("Improve it")

    assert result.state.status == WorkflowStatus.WAITING_FOR_CLARIFICATION
    assert result.state.pending_questions == ["Which validated outcome should be specified?"]
    assert not (tmp_path / "project" / "specifications" / "FEAT-0001.md").exists()
    assert (tmp_path / "project" / "discovery" / "REQ-0001" / "open-questions.md").is_file()


def test_discovery_workflow_resume_after_human_answers_writes_specification(tmp_path: Path) -> None:
    _seed_discovery_repo(tmp_path)
    workflow = DiscoveryWorkflow(tmp_path, runtime=_runtime_with_questions(True))
    suspended = workflow.start("Clarify generic outcome")

    resumed = workflow.resume_with_answers(
        suspended.state.request_id, "Use the first neutral outcome."
    )

    assert resumed.state.status == WorkflowStatus.WAITING_FOR_SPEC_APPROVAL
    assert resumed.state.pending_questions == []
    assert (tmp_path / "project" / "specifications" / "FEAT-0001.md").is_file()


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (DiscoveryVerdict.APPROVED, WorkflowStatus.COMPLETED),
        (DiscoveryVerdict.CHANGES_REQUESTED, WorkflowStatus.WAITING_FOR_CLARIFICATION),
        (DiscoveryVerdict.REJECTED, WorkflowStatus.REJECTED),
    ],
)
def test_discovery_product_owner_decisions_route_without_downstream_crews(
    tmp_path: Path, verdict: DiscoveryVerdict, expected: WorkflowStatus
) -> None:
    _seed_discovery_repo(tmp_path)
    workflow = DiscoveryWorkflow(tmp_path, runtime=FakeCrewRuntime())
    result = workflow.start("Add a clearly scoped generic capability")

    state = workflow.record_product_owner_decision(
        result.state.request_id, verdict, required_changes=("Adjust acceptance criteria.",)
    )

    assert state.status == expected
    assert state.status not in {WorkflowStatus.KNOWLEDGE_UPDATING, WorkflowStatus.DESIGN_RUNNING}


def test_discovery_permissions_and_read_only_tools_limit_unsafe_access(tmp_path: Path) -> None:
    _seed_discovery_repo(tmp_path)
    workflow = DiscoveryWorkflow(tmp_path, runtime=FakeCrewRuntime())
    workflow.start("Add a clearly scoped generic capability")
    with pytest.raises(PermissionError):
        workflow.artifacts.write_text("src/forbidden.py", "x")
    tools = RepositoryReadOnlyTools(tmp_path)
    with pytest.raises(ValueError):
        tools.read_text("../outside.txt")
    assert "pyproject.toml" in tools.dependency_summary()
    assert "src/module.py" in tools.list_files()


def _completed_runtime(
    crew_id: str, task_id: str, payload: dict[str, object] | None = None
) -> FakeCrewRuntime:
    return FakeCrewRuntime(
        result=CrewRunResult(
            crew_id=crew_id,
            status=CrewExecutionStatus.COMPLETED,
            task_results=[
                TaskRunResult(task_id=task_id, output="structured output", pydantic_output=payload)
            ],
            final_output="final structured output",
            message="completed",
        )
    )


def test_knowledge_writes_controlled_artifacts_and_rejects_validated_decisions(
    tmp_path: Path,
) -> None:
    runtime = _completed_runtime("knowledge", "collect_project_changes")

    result = KnowledgeCrew(tmp_path, runtime=runtime).kickoff(request_id="REQ-0001")

    assert result.status == CrewExecutionStatus.COMPLETED
    assert (tmp_path / "project" / "context.md").is_file()
    assert (
        runtime.requests[0].inputs["decision_boundary"] == "proposals_are_not_validated_decisions"
    )

    bad = FakeCrewRuntime(
        result=CrewRunResult(
            crew_id="knowledge",
            status=CrewExecutionStatus.COMPLETED,
            task_results=[
                TaskRunResult(task_id="audit_project_knowledge", output="validated decision")
            ],
        )
    )
    assert KnowledgeCrew(tmp_path, runtime=bad).kickoff().status == CrewExecutionStatus.FAILED


def test_design_requires_approved_specification_and_records_conditional_inputs(
    tmp_path: Path,
) -> None:
    runtime = _completed_runtime("design", "review_design")

    with pytest.raises(ValueError, match="approved specification"):
        DesignCrew(tmp_path, runtime=runtime).kickoff(specification_approved="false")

    result = DesignCrew(tmp_path, runtime=runtime).kickoff(
        request_id="REQ-0001", specification_approved="true", enable_ux="true"
    )

    assert result.status == CrewExecutionStatus.COMPLETED
    assert runtime.requests[-1].inputs["enable_ux"] == "true"
    assert runtime.requests[-1].inputs["enable_domain"] == "false"
    assert (tmp_path / "project" / "design" / "REQ-0001" / "review_design.md").is_file()


def test_planning_validates_acyclic_task_graph_and_writes_backlog_artifacts(tmp_path: Path) -> None:
    graph = PlanningGraph(
        tasks=[
            PlanningTask(id="TASK-1", title="Small task", verification="Run focused check"),
            PlanningTask(
                id="TASK-2",
                title="Small follow-up",
                verification="Run focused check",
                depends_on=["TASK-1"],
            ),
        ]
    )
    runtime = _completed_runtime("planning", "validate_task_graph", graph.model_dump())

    result = PlanningCrew(tmp_path, runtime=runtime).kickoff(
        request_id="REQ-0001", design_approved="true"
    )

    assert result.status == CrewExecutionStatus.COMPLETED
    assert runtime.requests[0].inputs["task_sizing"] == "small_verifiable_tasks"
    assert (tmp_path / "project" / "planning" / "REQ-0001" / "validate_task_graph.md").is_file()

    cyclic = PlanningGraph(
        tasks=[
            PlanningTask(id="TASK-1", title="A", verification="Check", depends_on=["TASK-2"]),
            PlanningTask(id="TASK-2", title="B", verification="Check", depends_on=["TASK-1"]),
        ]
    )
    bad_runtime = _completed_runtime("planning", "validate_task_graph", cyclic.model_dump())
    assert (
        PlanningCrew(tmp_path, runtime=bad_runtime).kickoff(design_approved="true").status
        == CrewExecutionStatus.FAILED
    )


def test_development_requires_single_safe_task_and_manifest(tmp_path: Path) -> None:
    manifest = DevelopmentManifest(task_id="TASK-1", changed_files=["src/allowed.py"]).model_dump()
    runtime = _completed_runtime("development", "prepare_implementation_manifest", manifest)

    with pytest.raises(ValueError, match="destructive"):
        DevelopmentCrew(tmp_path, task_paths=("src/allowed.py",), runtime=runtime).kickoff(
            command="rm -rf ."
        )

    result = DevelopmentCrew(tmp_path, task_paths=("src/allowed.py",), runtime=runtime).kickoff(
        task_id="TASK-1"
    )

    assert result.status == CrewExecutionStatus.COMPLETED
    assert runtime.requests[-1].inputs["command_runner"] == "safe_explicit_commands_only"
    assert (
        tmp_path / "project" / "development" / "TASK-1" / "prepare_implementation_manifest.md"
    ).is_file()

    missing_manifest = _completed_runtime("development", "self_review_implementation")
    assert (
        DevelopmentCrew(tmp_path, runtime=missing_manifest).kickoff().status
        == CrewExecutionStatus.FAILED
    )


def test_qa_requires_read_only_structured_matrix(tmp_path: Path) -> None:
    report = QAReport(
        verdict=QAVerdict.PASSED,
        tested_scope=["TASK-1"],
        evidence=["pytest passed"],
        acceptance_matrix=[
            AcceptanceMatrixRow(criterion="criterion", test="test", evidence="evidence")
        ],
    ).model_dump()
    runtime = _completed_runtime("qa", "write_qa_report", report)

    result = QaCrew(tmp_path, runtime=runtime).kickoff(task_id="TASK-1")

    assert result.status == CrewExecutionStatus.COMPLETED
    assert runtime.requests[0].inputs["code_access"] == "read_only"
    assert (tmp_path / "project" / "reviews" / "QA" / "TASK-1-write_qa_report.md").is_file()

    bad_report = {**report, "acceptance_matrix": []}
    assert (
        QaCrew(tmp_path, runtime=_completed_runtime("qa", "write_qa_report", bad_report))
        .kickoff()
        .status
        == CrewExecutionStatus.FAILED
    )


def test_review_refuses_failed_qa_and_requires_structured_verdict(tmp_path: Path) -> None:
    report = ReviewReport(verdict=ReviewVerdict.APPROVED, reviewed_scope=["TASK-1"]).model_dump()
    runtime = _completed_runtime("review", "issue_final_review", report)

    with pytest.raises(ValueError, match="QA FAILED or BLOCKED"):
        ReviewCrew(tmp_path, runtime=runtime).kickoff(qa_verdict=QAVerdict.FAILED.value)

    result = ReviewCrew(tmp_path, runtime=runtime).kickoff(
        request_id="REQ-0001", qa_verdict=QAVerdict.PASSED.value
    )

    assert result.status == CrewExecutionStatus.COMPLETED
    assert runtime.requests[-1].inputs["follow_up_policy"] == "proposals_not_approved_tasks"
    assert (
        tmp_path / "project" / "reviews" / "TECH" / "REQ-0001" / "issue_final_review.md"
    ).is_file()

    assert (
        ReviewCrew(tmp_path, runtime=_completed_runtime("review", "consolidate_review_findings"))
        .kickoff()
        .status
        == CrewExecutionStatus.FAILED
    )
