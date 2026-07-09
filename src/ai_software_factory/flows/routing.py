# mypy: ignore-errors
from ai_software_factory.models import QAVerdict, ReviewVerdict

VALID_TRANSITIONS = {
    "NEW": {"DISCOVERY_RUNNING"},
    "DISCOVERY_RUNNING": {"WAITING_FOR_CLARIFICATION", "WAITING_FOR_SPEC_APPROVAL", "FAILED"},
    "WAITING_FOR_CLARIFICATION": {"DISCOVERY_RUNNING"},
    "WAITING_FOR_SPEC_APPROVAL": {"KNOWLEDGE_UPDATING", "DISCOVERY_RUNNING", "REJECTED"},
    "KNOWLEDGE_UPDATING": {"DESIGN_RUNNING", "WAITING_FOR_PRODUCT_ACCEPTANCE", "COMPLETED"},
    "DESIGN_RUNNING": {"WAITING_FOR_DESIGN_APPROVAL", "PLANNING_RUNNING", "FAILED"},
    "WAITING_FOR_DESIGN_APPROVAL": {"PLANNING_RUNNING", "DESIGN_RUNNING", "REJECTED"},
    "PLANNING_RUNNING": {"WAITING_FOR_BACKLOG_APPROVAL", "FAILED"},
    "WAITING_FOR_BACKLOG_APPROVAL": {"DEVELOPMENT_RUNNING", "PLANNING_RUNNING", "REJECTED"},
    "DEVELOPMENT_RUNNING": {"QA_RUNNING", "FAILED"},
    "QA_RUNNING": {
        "REVIEW_RUNNING",
        "DEVELOPMENT_RUNNING",
        "WAITING_FOR_PRODUCT_ACCEPTANCE",
        "DESIGN_RUNNING",
    },
    "REVIEW_RUNNING": {
        "KNOWLEDGE_UPDATING",
        "DEVELOPMENT_RUNNING",
        "DESIGN_RUNNING",
        "WAITING_FOR_PRODUCT_ACCEPTANCE",
    },
    "WAITING_FOR_PRODUCT_ACCEPTANCE": {"COMPLETED", "REJECTED"},
    "COMPLETED": set(),
    "REJECTED": set(),
    "BLOCKED": set(),
    "FAILED": set(),
}


def assert_transition(current: str, target: str) -> None:
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition {current}->{target}")


def route_qa(verdict: QAVerdict, warnings_need_human: bool = False) -> str:
    return {
        QAVerdict.PASSED: "REVIEW_RUNNING",
        QAVerdict.PASSED_WITH_WARNINGS: "WAITING_FOR_PRODUCT_ACCEPTANCE"
        if warnings_need_human
        else "REVIEW_RUNNING",
        QAVerdict.FAILED: "DEVELOPMENT_RUNNING",
        QAVerdict.BLOCKED: "WAITING_FOR_PRODUCT_ACCEPTANCE",
    }[verdict]


def route_review(verdict: ReviewVerdict) -> str:
    return {
        ReviewVerdict.APPROVED: "KNOWLEDGE_UPDATING",
        ReviewVerdict.APPROVED_WITH_FOLLOW_UP: "KNOWLEDGE_UPDATING",
        ReviewVerdict.CHANGES_REQUESTED: "DEVELOPMENT_RUNNING",
        ReviewVerdict.REJECTED: "DESIGN_RUNNING",
    }[verdict]
