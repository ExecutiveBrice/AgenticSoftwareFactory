from __future__ import annotations

import subprocess
from pathlib import Path

_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".pyc"}
_MAX_FILE_BYTES = 64_000
_MAX_FILES = 500


class RepositoryReadOnlyTools:
    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path.resolve()

    def _resolve(self, relative_path: str | Path) -> Path:
        requested = Path(relative_path)
        if requested.is_absolute() or ".." in requested.parts:
            raise ValueError("Refusing unsafe repository path")
        path = (self.repository_path / requested).resolve()
        if self.repository_path not in (path, *path.parents):
            raise ValueError("Refusing access outside repository")
        return path

    def list_files(self) -> list[str]:
        files: list[str] = []
        for path in sorted(self.repository_path.rglob("*")):
            if len(files) >= _MAX_FILES:
                break
            rel = path.relative_to(self.repository_path)
            if not path.is_file() or self._ignored(rel) or self._binary(path):
                continue
            files.append(rel.as_posix())
        return files

    def read_text(self, relative_path: str | Path) -> str:
        path = self._resolve(relative_path)
        if self._binary(path) or path.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError("Refusing large or binary file")
        return path.read_text(encoding="utf-8", errors="replace")

    def search_text(self, pattern: str) -> dict[str, list[str]]:
        matches: dict[str, list[str]] = {}
        for rel in self.list_files():
            lines = [line for line in self.read_text(rel).splitlines() if pattern in line]
            if lines:
                matches[rel] = lines[:20]
        return matches

    def git_metadata(self) -> str:
        commands = [
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            ["git", "rev-parse", "--short", "HEAD"],
            ["git", "status", "--short"],
        ]
        parts: list[str] = []
        for command in commands:
            result = subprocess.run(
                command, cwd=self.repository_path, text=True, capture_output=True, check=False
            )
            parts.append(f"$ {' '.join(command)}\n{result.stdout.strip() or result.stderr.strip()}")
        return "\n\n".join(parts)

    def dependency_summary(self) -> str:
        summaries: list[str] = []
        for rel in ("pyproject.toml", "requirements.txt", "package.json"):
            path = self.repository_path / rel
            if path.is_file() and path.stat().st_size <= _MAX_FILE_BYTES:
                summaries.append(f"# {rel}\n{path.read_text(encoding='utf-8', errors='replace')}")
        return "\n\n".join(summaries) or "No dependency manifest found."

    def _ignored(self, rel: Path) -> bool:
        ignored = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        return any(part in ignored for part in rel.parts)

    def _binary(self, path: Path) -> bool:
        return path.suffix.lower() in _BINARY_SUFFIXES
