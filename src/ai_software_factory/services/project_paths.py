# mypy: ignore-errors
from pathlib import Path


class ProjectPaths:
    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path

    @property
    def project(self) -> Path:
        return self.repository_path / "project"
