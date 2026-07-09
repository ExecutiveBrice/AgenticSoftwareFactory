# mypy: ignore-errors
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: Path
    relative_path: str
    artifact_type: str = "document"
    exists: bool = True
