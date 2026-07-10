from pathlib import Path

from ai_software_factory.crews.shared.validation import load_crew_definition
from ai_software_factory.models import CrewDefinition, CrewExecutionResult, CrewExecutionStatus
from ai_software_factory.services import ArtifactService, policy_for_crew


class BaseCrew:
    crew_id: str

    def __init__(self, repository_path: Path, *, task_paths: tuple[str | Path, ...] = ()) -> None:
        self.repository_path = repository_path
        self.policy = policy_for_crew(self.crew_id, task_paths=task_paths)
        self.artifacts = ArtifactService(repository_path, policy=self.policy)

    def build(self) -> CrewDefinition:
        return load_crew_definition(self.crew_id)

    def kickoff(self, **kwargs: str) -> CrewExecutionResult:
        return CrewExecutionResult(
            crew_id=self.crew_id, status=CrewExecutionStatus.COMPLETED, message=str(kwargs)
        )
