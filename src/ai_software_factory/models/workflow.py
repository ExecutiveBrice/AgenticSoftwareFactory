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
    current_task_id: str | None = None
    qa_verdict: QAVerdict | None = None
    review_verdict: ReviewVerdict | None = None
    pending_questions: list[str] = Field(default_factory=list)
    human_requests: list[HumanRequestRecord] = Field(default_factory=list)
    transition_history: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
