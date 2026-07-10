from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .verdict import QAVerdict, ReviewVerdict


class WorkflowStatus(StrEnum):
    NEW = "NEW"
    DISCOVERY_RUNNING = "DISCOVERY_RUNNING"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    WAITING_FOR_SPEC_APPROVAL = "WAITING_FOR_SPEC_APPROVAL"
    KNOWLEDGE_UPDATING = "KNOWLEDGE_UPDATING"
    DESIGN_RUNNING = "DESIGN_RUNNING"
    WAITING_FOR_DESIGN_APPROVAL = "WAITING_FOR_DESIGN_APPROVAL"
    PLANNING_RUNNING = "PLANNING_RUNNING"
    WAITING_FOR_BACKLOG_APPROVAL = "WAITING_FOR_BACKLOG_APPROVAL"
    DEVELOPMENT_RUNNING = "DEVELOPMENT_RUNNING"
    QA_RUNNING = "QA_RUNNING"
    REVIEW_RUNNING = "REVIEW_RUNNING"
    WAITING_FOR_PRODUCT_ACCEPTANCE = "WAITING_FOR_PRODUCT_ACCEPTANCE"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class HumanRequestType(StrEnum):
    CLARIFICATION = "CLARIFICATION"
    APPROVAL = "APPROVAL"


class HumanRequestStatus(StrEnum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class DesignDecision(StrEnum):
    STRUCTURAL_DECISION = "STRUCTURAL_DECISION"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    PRODUCT_DECISION_MISSING = "PRODUCT_DECISION_MISSING"


class PlanningDecision(StrEnum):
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"


class DevelopmentDecision(StrEnum):
    TASK_SUCCEEDED = "TASK_SUCCEEDED"
    CHECKS_FAILED = "CHECKS_FAILED"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    FAILED = "FAILED"


class ProductAcceptanceDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class WorkflowStep(StrEnum):
    DISCOVERY = "DISCOVERY"
    KNOWLEDGE_BEFORE_DESIGN = "KNOWLEDGE_BEFORE_DESIGN"
    DESIGN = "DESIGN"
    PLANNING = "PLANNING"
    DEVELOPMENT = "DEVELOPMENT"
    QA = "QA"
    REVIEW = "REVIEW"
    KNOWLEDGE_FINAL = "KNOWLEDGE_FINAL"
    PRODUCT_ACCEPTANCE = "PRODUCT_ACCEPTANCE"


class FlowTransitionEvent(StrEnum):
    START_REQUEST = "START_REQUEST"
    DISCOVERY_QUESTIONS = "DISCOVERY_QUESTIONS"
    DISCOVERY_APPROVED = "DISCOVERY_APPROVED"
    DISCOVERY_CHANGES_REQUESTED = "DISCOVERY_CHANGES_REQUESTED"
    DISCOVERY_REJECTED = "DISCOVERY_REJECTED"
    KNOWLEDGE_UPDATED = "KNOWLEDGE_UPDATED"
    DESIGN_DECISION = "DESIGN_DECISION"
    PLANNING_DECISION = "PLANNING_DECISION"
    DEVELOPMENT_DECISION = "DEVELOPMENT_DECISION"
    QA_VERDICT = "QA_VERDICT"
    REVIEW_VERDICT = "REVIEW_VERDICT"
    PRODUCT_ACCEPTANCE = "PRODUCT_ACCEPTANCE"


class FlowTransitionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event: FlowTransitionEvent
    source: WorkflowStatus
    target: WorkflowStatus
    detail: str | None = None
    task_id: str | None = None
    date: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HumanDecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str
    answer: str | None = None
    date: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HumanRequestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    request_id: str
    stage: WorkflowStatus
    type: HumanRequestType
    question_or_decision: str
    valid_options: list[str] = Field(default_factory=list)
    context: dict[str, str] = Field(default_factory=dict)
    artifact_paths: list[Path] = Field(default_factory=list)
    date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: HumanRequestStatus = HumanRequestStatus.PENDING
    decisions: list[HumanDecisionRecord] = Field(default_factory=list)


class WorkflowState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    feature_id: str | None = None
    repository_path: Path
    current_stage: WorkflowStatus = WorkflowStatus.NEW
    status: WorkflowStatus = WorkflowStatus.NEW
    specification_path: Path | None = None
    design_paths: list[Path] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    completed_task_ids: list[str] = Field(default_factory=list)
    current_task_id: str | None = None
    qa_verdict: QAVerdict | None = None
    review_verdict: ReviewVerdict | None = None
    pending_questions: list[str] = Field(default_factory=list)
    human_requests: list[HumanRequestRecord] = Field(default_factory=list)
    transition_history: list[str] = Field(default_factory=list)
    transitions: list[FlowTransitionRecord] = Field(default_factory=list)
    completed_steps: list[WorkflowStep] = Field(default_factory=list)
    loop_count: int = 0
    max_loops: int = 5
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
