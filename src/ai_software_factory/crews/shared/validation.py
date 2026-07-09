from importlib import resources

from ai_software_factory.models import AgentDefinition, CrewDefinition, TaskDefinition


def _load_mapping(text: str, root: str) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    current: str | None = None
    in_root = False
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line == f"{root}:":
            in_root = True
            continue
        if not in_root:
            continue
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current = line.strip()[:-1]
            result[current] = {}
            continue
        if current and line.startswith("    ") and ":" in line:
            key, value = line.strip().split(":", 1)
            clean = value.strip()
            result[current][key] = [] if clean == "[]" else clean
    return result


def load_crew_definition(crew_id: str) -> CrewDefinition:
    base = resources.files("ai_software_factory.resources.crews").joinpath(crew_id)
    agents_text = base.joinpath("agents.yaml").read_text(encoding="utf-8")
    tasks_text = base.joinpath("tasks.yaml").read_text(encoding="utf-8")
    agents = [AgentDefinition(id=k, **v) for k, v in _load_mapping(agents_text, "agents").items()]
    tasks = [TaskDefinition(id=k, **v) for k, v in _load_mapping(tasks_text, "tasks").items()]
    agent_ids = {a.id for a in agents}
    missing = [t.id for t in tasks if t.agent not in agent_ids]
    if missing:
        raise ValueError(f"Tasks reference unknown agents: {missing}")
    return CrewDefinition(id=crew_id, description=crew_id, agents=agents, tasks=tasks)
