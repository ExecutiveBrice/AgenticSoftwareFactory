from collections.abc import Mapping
from importlib import resources
from typing import Any

import yaml  # type: ignore[import-untyped]

from ai_software_factory.models import AgentDefinition, CrewDefinition, TaskDefinition
from pydantic import ValidationError


class CrewYamlValidationError(ValueError):
    """Raised when a crew YAML resource cannot be loaded or validated."""

    def __init__(self, crew_id: str, file_name: str, field: str, explanation: str) -> None:
        self.crew_id = crew_id
        self.file_name = file_name
        self.field = field
        self.explanation = explanation
        super().__init__(
            f"Invalid crew YAML for crew '{crew_id}' in {file_name}, field '{field}': {explanation}"
        )


def _load_yaml_resource(crew_id: str, file_name: str) -> Mapping[str, Any]:
    base = resources.files("ai_software_factory.resources.crews").joinpath(crew_id)
    resource = base.joinpath(file_name)
    try:
        text = resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CrewYamlValidationError(
            crew_id, file_name, file_name, "required YAML resource is missing"
        ) from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CrewYamlValidationError(
            crew_id, file_name, "$", f"invalid YAML syntax: {exc}"
        ) from exc
    if loaded is None:
        raise CrewYamlValidationError(crew_id, file_name, "$", "document must not be empty")
    if not isinstance(loaded, Mapping):
        raise CrewYamlValidationError(crew_id, file_name, "$", "document root must be a mapping")
    return loaded


def _expect_mapping(
    crew_id: str, file_name: str, data: Mapping[str, Any], root: str
) -> Mapping[str, Any]:
    allowed_roots = {root, "description"}
    unexpected_roots = set(data) - allowed_roots
    if unexpected_roots or root not in data:
        raise CrewYamlValidationError(
            crew_id,
            file_name,
            "$",
            f"document root must contain '{root}' and no unexpected keys",
        )
    value = data[root]
    if not isinstance(value, Mapping) or not value:
        raise CrewYamlValidationError(
            crew_id, file_name, root, f"'{root}' must be a non-empty mapping"
        )
    return value


def _format_validation_error(error: ValidationError) -> tuple[str, str]:
    first = error.errors()[0]
    loc = first["loc"]
    field = ".".join(str(part) for part in loc) if isinstance(loc, tuple | list) else str(loc)
    return field, str(first["msg"])


def _load_agents(crew_id: str) -> list[AgentDefinition]:
    mapping = _expect_mapping(
        crew_id, "agents.yaml", _load_yaml_resource(crew_id, "agents.yaml"), "agents"
    )
    agents: list[AgentDefinition] = []
    for agent_id, payload in mapping.items():
        if not isinstance(payload, Mapping):
            raise CrewYamlValidationError(
                crew_id, "agents.yaml", str(agent_id), "agent must be a mapping"
            )
        missing = [field for field in ("role", "goal", "backstory") if field not in payload]
        if missing:
            raise CrewYamlValidationError(
                crew_id,
                "agents.yaml",
                f"agents.{agent_id}.{missing[0]}",
                f"required field '{missing[0]}' is missing",
            )
        try:
            agents.append(AgentDefinition(id=str(agent_id), **payload))
        except ValidationError as exc:
            field, explanation = _format_validation_error(exc)
            raise CrewYamlValidationError(
                crew_id, "agents.yaml", f"agents.{agent_id}.{field}", explanation
            ) from exc
    return agents


def _load_tasks(crew_id: str) -> list[TaskDefinition]:
    mapping = _expect_mapping(
        crew_id, "tasks.yaml", _load_yaml_resource(crew_id, "tasks.yaml"), "tasks"
    )
    tasks: list[TaskDefinition] = []
    for task_id, payload in mapping.items():
        if not isinstance(payload, Mapping):
            raise CrewYamlValidationError(
                crew_id, "tasks.yaml", str(task_id), "task must be a mapping"
            )
        missing = [
            field for field in ("description", "expected_output", "agent") if field not in payload
        ]
        if missing:
            raise CrewYamlValidationError(
                crew_id,
                "tasks.yaml",
                f"tasks.{task_id}.{missing[0]}",
                f"required field '{missing[0]}' is missing",
            )
        try:
            tasks.append(TaskDefinition(id=str(task_id), **payload))
        except ValidationError as exc:
            field, explanation = _format_validation_error(exc)
            raise CrewYamlValidationError(
                crew_id, "tasks.yaml", f"tasks.{task_id}.{field}", explanation
            ) from exc
    return tasks


def _validate_references(
    crew_id: str, agents: list[AgentDefinition], tasks: list[TaskDefinition]
) -> None:
    agent_ids = {agent.id for agent in agents}
    task_ids = {task.id for task in tasks}
    for task in tasks:
        if task.agent not in agent_ids:
            raise CrewYamlValidationError(
                crew_id,
                "tasks.yaml",
                f"tasks.{task.id}.agent",
                f"references unknown agent '{task.agent}'",
            )
        for context_id in task.context:
            if context_id not in task_ids:
                raise CrewYamlValidationError(
                    crew_id,
                    "tasks.yaml",
                    f"tasks.{task.id}.context",
                    f"references unknown task '{context_id}'",
                )
    _validate_acyclic_contexts(crew_id, tasks)


def _validate_acyclic_contexts(crew_id: str, tasks: list[TaskDefinition]) -> None:
    graph = {task.id: task.context for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, path: list[str]) -> None:
        if task_id in visiting:
            cycle = " -> ".join([*path, task_id])
            raise CrewYamlValidationError(
                crew_id,
                "tasks.yaml",
                f"tasks.{task_id}.context",
                f"context graph contains a cycle: {cycle}",
            )
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph[task_id]:
            visit(dependency, [*path, task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task.id, [])


def load_crew_definition(crew_id: str) -> CrewDefinition:
    agents = _load_agents(crew_id)
    tasks = _load_tasks(crew_id)
    _validate_references(crew_id, agents, tasks)
    return CrewDefinition(id=crew_id, description=crew_id, agents=agents, tasks=tasks)
