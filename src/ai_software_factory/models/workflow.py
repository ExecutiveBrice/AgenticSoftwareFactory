# mypy: ignore-errors
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .verdict import QAVerdict, ReviewVerdict


class WorkflowState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    feature_id: str | None = None
    repository_path: Path
    current_stage: str = "NEW"
    status: str = "NEW"
    specification_path: Path | None = None
    design_paths: list[Path] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    current_task_id: str | None = None
    qa_verdict: QAVerdict | None = None
    review_verdict: ReviewVerdict | None = None
    pending_questions: list[str] = Field(default_factory=list)
    transition_history: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
