# mypy: ignore-errors
from pathlib import Path

from ai_software_factory.models import ArtifactReference


class ArtifactService:
    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path.resolve()

    def resolve(self, relative_path: str | Path) -> Path:
        path = (
            (self.repository_path / relative_path).resolve()
            if not Path(relative_path).is_absolute()
            else Path(relative_path).resolve()
        )
        if self.repository_path not in (path, *path.parents):
            raise ValueError("Refusing access outside repository")
        return path

    def exists(self, relative_path: str | Path) -> bool:
        return self.resolve(relative_path).exists()

    def write_text(
        self,
        relative_path: str | Path,
        content: str,
        *,
        overwrite: bool = False,
        artifact_type: str = "document",
    ) -> ArtifactReference:
        path = self.resolve(relative_path)
        if path.exists() and not overwrite:
            raise FileExistsError(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ArtifactReference(
            path=path,
            relative_path=str(path.relative_to(self.repository_path)),
            artifact_type=artifact_type,
            exists=True,
        )

    def reference(
        self, relative_path: str | Path, *, artifact_type: str = "document"
    ) -> ArtifactReference:
        path = self.resolve(relative_path)
        return ArtifactReference(
            path=path,
            relative_path=str(path.relative_to(self.repository_path)),
            artifact_type=artifact_type,
            exists=path.exists(),
        )
