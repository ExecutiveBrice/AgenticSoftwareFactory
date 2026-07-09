from pathlib import Path

from ai_software_factory.crews.shared.validation import load_crew_definition
from ai_software_factory.models import CrewDefinition, CrewExecutionResult, CrewExecutionStatus
from ai_software_factory.services import ArtifactService


class BaseCrew:
    crew_id: str
    allowed_write_roots: tuple[str, ...] = ("project/",)

    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path
        self.artifacts = ArtifactService(repository_path)

    def build(self) -> CrewDefinition:
        return load_crew_definition(self.crew_id)

    def _check_write(self, relative_path: str) -> None:
        if not any(relative_path.startswith(root) for root in self.allowed_write_roots):
            raise PermissionError(relative_path)

    def kickoff(self, **kwargs: str) -> CrewExecutionResult:
        return CrewExecutionResult(
            crew_id=self.crew_id, status=CrewExecutionStatus.COMPLETED, message=str(kwargs)
        )
