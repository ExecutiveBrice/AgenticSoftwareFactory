# mypy: ignore-errors
from pydantic import BaseModel, ConfigDict


class CrewContext(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    repository_path: str
