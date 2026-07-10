from pathlib import Path

from ai_software_factory.models import ArtifactReference
from ai_software_factory.services.repository_policy import (
    PermissionAction,
    RepositoryPermissionPolicy,
)


class ArtifactService:
    def __init__(
        self, repository_path: Path, policy: RepositoryPermissionPolicy | None = None
    ) -> None:
        self.repository_path = repository_path.resolve()
        self.policy = policy

    def resolve(self, relative_path: str | Path) -> Path:
        requested = Path(relative_path)
        if requested.is_absolute() or ".." in requested.parts:
            raise ValueError("Refusing unsafe repository path")
        base_path = self.repository_path / requested
        existing_anchor = base_path if base_path.exists() else base_path.parent
        path = (
            existing_anchor.resolve() / base_path.name
            if not base_path.exists()
            else base_path.resolve()
        )
        if self.repository_path not in (path, *path.parents):
            raise ValueError("Refusing access outside repository")
        return path

    def _relative(self, path: Path) -> Path:
        return path.relative_to(self.repository_path)

    def _require(self, action: PermissionAction, path: Path) -> None:
        if self.policy is not None:
            self.policy.require(action, self._relative(path))

    def exists(self, relative_path: str | Path) -> bool:
        path = self.resolve(relative_path)
        self._require(PermissionAction.READ, path)
        return path.exists()

    def read_text(self, relative_path: str | Path) -> str:
        path = self.resolve(relative_path)
        self._require(PermissionAction.READ, path)
        return path.read_text(encoding="utf-8")

    def write_text(
        self,
        relative_path: str | Path,
        content: str,
        *,
        overwrite: bool = False,
        artifact_type: str = "document",
    ) -> ArtifactReference:
        path = self.resolve(relative_path)
        action = PermissionAction.MODIFY if path.exists() else PermissionAction.CREATE
        self._require(action, path)
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

    def delete(self, relative_path: str | Path) -> None:
        path = self.resolve(relative_path)
        self._require(PermissionAction.DELETE, path)
        path.unlink()

    def reference(
        self, relative_path: str | Path, *, artifact_type: str = "document"
    ) -> ArtifactReference:
        path = self.resolve(relative_path)
        self._require(PermissionAction.READ, path)
        return ArtifactReference(
            path=path,
            relative_path=str(path.relative_to(self.repository_path)),
            artifact_type=artifact_type,
            exists=path.exists(),
        )
