from ai_software_factory.models import QAVerdict, ReviewVerdict, WorkflowStatus

VALID_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.NEW: {WorkflowStatus.DISCOVERY_RUNNING},
    WorkflowStatus.DISCOVERY_RUNNING: {
        WorkflowStatus.WAITING_FOR_CLARIFICATION,
        WorkflowStatus.WAITING_FOR_SPEC_APPROVAL,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.WAITING_FOR_CLARIFICATION: {WorkflowStatus.DISCOVERY_RUNNING},
    WorkflowStatus.WAITING_FOR_SPEC_APPROVAL: {
        WorkflowStatus.KNOWLEDGE_UPDATING,
        WorkflowStatus.DISCOVERY_RUNNING,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.KNOWLEDGE_UPDATING: {
        WorkflowStatus.DESIGN_RUNNING,
        WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
        WorkflowStatus.COMPLETED,
    },
    WorkflowStatus.DESIGN_RUNNING: {
        WorkflowStatus.DESIGN_RUNNING,
        WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL,
        WorkflowStatus.PLANNING_RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.BLOCKED,
    },
    WorkflowStatus.WAITING_FOR_DESIGN_APPROVAL: {
        WorkflowStatus.PLANNING_RUNNING,
        WorkflowStatus.DESIGN_RUNNING,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.PLANNING_RUNNING: {
        WorkflowStatus.PLANNING_RUNNING,
        WorkflowStatus.WAITING_FOR_BACKLOG_APPROVAL,
        WorkflowStatus.REJECTED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.WAITING_FOR_BACKLOG_APPROVAL: {
        WorkflowStatus.DEVELOPMENT_RUNNING,
        WorkflowStatus.PLANNING_RUNNING,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.DEVELOPMENT_RUNNING: {
        WorkflowStatus.DEVELOPMENT_RUNNING,
        WorkflowStatus.QA_RUNNING,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.QA_RUNNING: {
        WorkflowStatus.REVIEW_RUNNING,
        WorkflowStatus.DEVELOPMENT_RUNNING,
        WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
        WorkflowStatus.DESIGN_RUNNING,
    },
    WorkflowStatus.REVIEW_RUNNING: {
        WorkflowStatus.KNOWLEDGE_UPDATING,
        WorkflowStatus.DEVELOPMENT_RUNNING,
        WorkflowStatus.DESIGN_RUNNING,
        WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
    },
    WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE: {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.REJECTED: set(),
    WorkflowStatus.BLOCKED: {
        WorkflowStatus.DESIGN_RUNNING,
        WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
    },
    WorkflowStatus.FAILED: set(),
}


def assert_transition(current: WorkflowStatus, target: WorkflowStatus) -> None:
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition {current}->{target}")


def route_qa(verdict: QAVerdict, warnings_need_human: bool = False) -> WorkflowStatus:
    return {
        QAVerdict.PASSED: WorkflowStatus.REVIEW_RUNNING,
        QAVerdict.PASSED_WITH_WARNINGS: WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE
        if warnings_need_human
        else WorkflowStatus.REVIEW_RUNNING,
        QAVerdict.FAILED: WorkflowStatus.DEVELOPMENT_RUNNING,
        QAVerdict.BLOCKED: WorkflowStatus.WAITING_FOR_PRODUCT_ACCEPTANCE,
    }[verdict]


def route_review(verdict: ReviewVerdict) -> WorkflowStatus:
    return {
        ReviewVerdict.APPROVED: WorkflowStatus.KNOWLEDGE_UPDATING,
        ReviewVerdict.APPROVED_WITH_FOLLOW_UP: WorkflowStatus.KNOWLEDGE_UPDATING,
        ReviewVerdict.CHANGES_REQUESTED: WorkflowStatus.DEVELOPMENT_RUNNING,
        ReviewVerdict.REJECTED: WorkflowStatus.DESIGN_RUNNING,
    }[verdict]
