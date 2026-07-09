# mypy: ignore-errors
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .artifact import ArtifactReference


class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    role: str
    goal: str
    backstory: str = ""


class TaskDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    description: str
    expected_output: str
    agent: str
    context: list[str] = Field(default_factory=list)
    output_path: str | None = None
    optional: bool = False


class CrewDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    description: str
    agents: list[AgentDefinition]
    tasks: list[TaskDefinition]


class HumanValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    context: str
    questions: list[str] = Field(default_factory=list)
    valid_options: list[str] = Field(default_factory=list)
    stage: str
    artifact_paths: list[Path] = Field(default_factory=list)


class HumanValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    decision: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)


class CrewExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    crew_id: str
    status: str
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)
    human_validation: HumanValidationRequest | None = None
    message: str = ""
