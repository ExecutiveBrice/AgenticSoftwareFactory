from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ai_software_factory.crews.registry import CrewRegistry
from ai_software_factory.crews.shared import validation as crew_validation
from ai_software_factory.crews.shared.constants import CREW_IDS
from ai_software_factory.crews.shared.validation import (
    CrewYamlValidationError,
    load_crew_definition,
)
from ai_software_factory.flows import FactoryFlow
from ai_software_factory.flows.routing import assert_transition, route_qa, route_review
from ai_software_factory.models import (
    AgentDefinition,
    CrewDefinition,
    DiscoveryVerdict,
    QAVerdict,
    ReviewVerdict,
    WorkflowState,
)
from ai_software_factory.services import ArtifactService, IdentifierService


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
