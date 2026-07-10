from pydantic import BaseModel, ConfigDict, Field

from .verdict import DiscoveryVerdict, QAVerdict, ReviewVerdict


class DiscoveryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    question: str
    reason: str
    impact: str
    options: list[str] = Field(default_factory=list)
    blocking: bool = True


class DiscoveryQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    questions: list[DiscoveryQuestion] = Field(default_factory=list)
    can_continue_without_human: bool = False


class ProductOwnerDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    verdict: DiscoveryVerdict
    specification_path: str
    required_changes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class AcceptanceMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    criterion: str
    test: str
    evidence: str


class QAReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    verdict: QAVerdict
    tested_scope: list[str]
    evidence: list[str]
    acceptance_matrix: list[AcceptanceMatrixRow] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    verdict: ReviewVerdict
    reviewed_scope: list[str]
    findings: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


class DevelopmentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: str
    changed_files: list[str]
    tests_added_or_updated: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)


class PlanningTask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    title: str
    verification: str
    depends_on: list[str] = Field(default_factory=list)


class PlanningGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tasks: list[PlanningTask]
