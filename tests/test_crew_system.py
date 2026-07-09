from pathlib import Path

import pytest

from ai_software_factory.crews.registry import CrewRegistry
from ai_software_factory.crews.shared.constants import CREW_IDS
from ai_software_factory.crews.shared.validation import load_crew_definition
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
        id="x", description="x", agents=[AgentDefinition(id="a", role="r", goal="g")], tasks=[]
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
