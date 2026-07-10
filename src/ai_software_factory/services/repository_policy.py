from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

LOGGER = logging.getLogger(__name__)


class PermissionAction(StrEnum):
    READ = "read"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


@dataclass(frozen=True)
class PathRule:
    path: Path
    recursive: bool = False

    @classmethod
    def exact(cls, path: str) -> Self:
        return cls(Path(path), recursive=False)

    @classmethod
    def under(cls, path: str) -> Self:
        return cls(Path(path), recursive=True)

    def allows(self, relative_path: Path) -> bool:
        if self.recursive:
            return relative_path == self.path or self.path in relative_path.parents
        return relative_path == self.path


@dataclass(frozen=True)
class RepositoryPermissionPolicy:
    crew_id: str
    read: tuple[PathRule, ...]
    create: tuple[PathRule, ...]
    modify: tuple[PathRule, ...]
    delete: tuple[PathRule, ...] = ()

    def rules_for(self, action: PermissionAction) -> tuple[PathRule, ...]:
        if action is PermissionAction.READ:
            return self.read
        if action is PermissionAction.CREATE:
            return self.create
        if action is PermissionAction.MODIFY:
            return self.modify
        return self.delete

    def allows(self, action: PermissionAction, relative_path: Path) -> bool:
        return any(rule.allows(relative_path) for rule in self.rules_for(action))

    def require(self, action: PermissionAction, relative_path: Path) -> None:
        if not self.allows(action, relative_path):
            LOGGER.warning(
                "Repository permission denied",
                extra={"crew_id": self.crew_id, "action": action.value, "path": str(relative_path)},
            )
            raise PermissionError(f"{self.crew_id} cannot {action.value} {relative_path}")


def _repo_read() -> tuple[PathRule, ...]:
    return (PathRule.under("."),)


_DISCOVERY = (PathRule.under("project/discovery"), PathRule.under("project/specifications"))
_KNOWLEDGE_FILES = (
    PathRule.exact("project/context.md"),
    PathRule.exact("project/glossary.md"),
    PathRule.exact("project/roadmap.md"),
    PathRule.exact("project/changelog.md"),
)
_KNOWLEDGE_REPORTS = (
    PathRule.under("project/reviews/KNOWLEDGE"),
    PathRule.under("project/reports/knowledge"),
)
_DESIGN = (PathRule.under("project/architecture"), PathRule.under("project/design"))
_PLANNING = (PathRule.under("project/backlog"), PathRule.under("project/planning"))
_QA = (PathRule.under("project/reviews/QA"), PathRule.under("project/reports/qa"))
_REVIEW = (PathRule.under("project/reviews/TECH"), PathRule.under("project/reports/tech"))
_DEV_ARTIFACTS = (PathRule.under("project/development"), PathRule.under("project/reviews/DEV"))


def policy_for_crew(
    crew_id: str, *, task_paths: tuple[str | Path, ...] = ()
) -> RepositoryPermissionPolicy:
    task_rules = tuple(PathRule.exact(str(path)) for path in task_paths)
    if crew_id == "discovery":
        return RepositoryPermissionPolicy(crew_id, _repo_read(), _DISCOVERY, _DISCOVERY)
    if crew_id == "knowledge":
        rules: tuple[PathRule, ...] = (
            _KNOWLEDGE_FILES + (PathRule.under("project/decisions"),) + _KNOWLEDGE_REPORTS
        )
        return RepositoryPermissionPolicy(crew_id, _repo_read(), rules, rules)
    if crew_id == "design":
        return RepositoryPermissionPolicy(crew_id, _repo_read(), _DESIGN, _DESIGN)
    if crew_id == "planning":
        return RepositoryPermissionPolicy(crew_id, _repo_read(), _PLANNING, _PLANNING)
    if crew_id == "development":
        rules = task_rules + _DEV_ARTIFACTS
        return RepositoryPermissionPolicy(crew_id, _repo_read(), rules, rules, task_rules)
    if crew_id == "qa":
        return RepositoryPermissionPolicy(crew_id, _repo_read(), _QA, _QA)
    if crew_id == "review":
        return RepositoryPermissionPolicy(crew_id, _repo_read(), _REVIEW, _REVIEW)
    raise ValueError(f"Unknown crew: {crew_id}")
