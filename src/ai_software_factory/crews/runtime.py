from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from ai_software_factory.models import CrewDefinition, CrewExecutionStatus
from pydantic import BaseModel, ConfigDict, Field


class _CrewAIObjectFactory(Protocol):
    def __call__(self, **kwargs: object) -> object: ...


class _CrewAIProcess(Protocol):
    sequential: object


class _CrewAIObject(Protocol):
    def kickoff(self, *, inputs: dict[str, str]) -> object: ...


class _CrewAIModule(Protocol):
    Agent: _CrewAIObjectFactory
    Task: _CrewAIObjectFactory
    Crew: Callable[..., _CrewAIObject]
    Process: _CrewAIProcess


class TaskRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str
    output: str = ""
    status: CrewExecutionStatus = CrewExecutionStatus.COMPLETED
    message: str = ""
    pydantic_output: dict[str, object] | None = None


class CrewRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    crew_id: str
    repository_path: Path
    definition: CrewDefinition
    inputs: dict[str, str] = Field(default_factory=dict)


class CrewRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    crew_id: str
    status: CrewExecutionStatus
    task_results: list[TaskRunResult] = Field(default_factory=list)
    message: str = ""
    final_output: str = ""
    usage_metrics: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class CrewRuntime(Protocol):
    def run(self, request: CrewRunRequest) -> CrewRunResult:
        """Execute a crew through an adapter and return a typed result."""


class CrewRuntimeFactory(Protocol):
    def create(self, crew_id: str) -> CrewRuntime:
        """Return the runtime to use for a crew."""


class FakeCrewRuntime:
    """Deterministic runtime used by tests without any external service."""

    def __init__(self, *, result: CrewRunResult | None = None) -> None:
        self._result = result
        self.requests: list[CrewRunRequest] = []

    def run(self, request: CrewRunRequest) -> CrewRunResult:
        self.requests.append(request)
        if self._result is not None:
            return self._result
        task_results = [
            TaskRunResult(
                task_id=task.id,
                output=f"fake output for {request.crew_id}.{task.id}",
                status=CrewExecutionStatus.COMPLETED,
            )
            for task in request.definition.tasks
        ]
        final_output = task_results[-1].output if task_results else ""
        return CrewRunResult(
            crew_id=request.crew_id,
            status=CrewExecutionStatus.COMPLETED,
            task_results=task_results,
            final_output=final_output,
            message="Fake crew runtime completed deterministically.",
        )


class FakeCrewRuntimeFactory:
    def __init__(self, runtimes: Mapping[str, FakeCrewRuntime] | None = None) -> None:
        self._runtimes = dict(runtimes or {})
        self.created_for: list[str] = []

    def create(self, crew_id: str) -> FakeCrewRuntime:
        self.created_for.append(crew_id)
        runtime = self._runtimes.get(crew_id)
        if runtime is not None:
            return runtime
        runtime = FakeCrewRuntime()
        self._runtimes[crew_id] = runtime
        return runtime


class DisabledCrewRuntime:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = (
            reason or "Crew execution is disabled because CrewAI is not installed or configured."
        )

    def run(self, request: CrewRunRequest) -> CrewRunResult:
        return CrewRunResult(
            crew_id=request.crew_id,
            status=CrewExecutionStatus.FAILED,
            task_results=[],
            message=self.reason,
            error=self.reason,
        )


class DisabledCrewRuntimeFactory:
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    def create(self, crew_id: str) -> DisabledCrewRuntime:
        return DisabledCrewRuntime(self.reason)


def _dump_pydantic(value: object) -> dict[str, object] | None:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _string_output(value: object) -> str:
    raw = getattr(value, "raw", None)
    if isinstance(raw, str):
        return raw
    if isinstance(value, str):
        return value
    return str(value) if value is not None else ""


class CrewAIConfig(BaseModel):
    """Runtime-only CrewAI adapter configuration."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    llm: object | None = None
    verbose: bool = False


class CrewAIConfigurationError(RuntimeError):
    """Raised when the real CrewAI runtime cannot be configured safely."""


class CrewAIRuntime:
    """Real CrewAI runtime adapter behind the CrewRuntime port."""

    def __init__(self, config: CrewAIConfig | None = None) -> None:
        self.config = config or CrewAIConfig()
        if self.config.llm is None:
            raise CrewAIConfigurationError("CrewAI runtime requires an explicit LLM configuration.")

    def run(self, request: CrewRunRequest) -> CrewRunResult:
        try:
            crew = self.build_crew(request.definition)
            output = crew.kickoff(inputs=request.inputs)
        except Exception as exc:
            return CrewRunResult(
                crew_id=request.crew_id,
                status=CrewExecutionStatus.FAILED,
                message=f"CrewAI execution failed: {exc}",
                error=str(exc),
            )
        return self._convert_crew_output(request.crew_id, output)

    def build_crew(self, definition: CrewDefinition) -> _CrewAIObject:
        crewai = self._crewai_module()
        agents = self.build_agents(definition)
        tasks = self.build_tasks(definition, agents)
        return crewai.Crew(
            agents=list(agents.values()),
            tasks=list(tasks.values()),
            process=crewai.Process.sequential,
            verbose=self.config.verbose,
        )

    def build_agents(self, definition: CrewDefinition) -> dict[str, object]:
        crewai = self._crewai_module()
        return {
            agent.id: crewai.Agent(
                role=agent.role,
                goal=agent.goal,
                backstory=agent.backstory,
                allow_delegation=agent.allow_delegation,
                verbose=agent.verbose,
                max_iter=agent.max_iter,
                respect_context_window=agent.respect_context_window,
                llm=self.config.llm,
                tools=[],
                allow_code_execution=False,
            )
            for agent in definition.agents
        }

    def build_tasks(
        self, definition: CrewDefinition, agents: Mapping[str, object]
    ) -> dict[str, object]:
        crewai = self._crewai_module()
        tasks: dict[str, object] = {}
        for task in definition.tasks:
            kwargs: dict[str, object] = {
                "description": task.description,
                "expected_output": task.expected_output,
                "agent": agents[task.agent],
                "context": [tasks[context_id] for context_id in task.context],
                "async_execution": False,
                "human_input": task.human_input,
                "markdown": task.markdown,
            }
            if task.output_file is not None:
                kwargs["output_file"] = task.output_file
            elif task.output_path is not None:
                kwargs["output_file"] = task.output_path
            output_model = self._output_model(task.output_model)
            if output_model is not None:
                kwargs["output_pydantic"] = output_model
            tasks[task.id] = crewai.Task(**kwargs)
        return tasks

    def _convert_crew_output(self, crew_id: str, output: object) -> CrewRunResult:
        raw_tasks = getattr(output, "tasks_output", None) or []
        task_results = [
            TaskRunResult(
                task_id=str(
                    getattr(task_output, "name", None)
                    or getattr(task_output, "task_id", None)
                    or index
                ),
                output=_string_output(task_output),
                pydantic_output=_dump_pydantic(getattr(task_output, "pydantic", None)),
            )
            for index, task_output in enumerate(raw_tasks)
        ]
        usage = getattr(output, "usage_metrics", None) or getattr(output, "token_usage", None) or {}
        return CrewRunResult(
            crew_id=crew_id,
            status=CrewExecutionStatus.COMPLETED,
            task_results=task_results,
            final_output=_string_output(output),
            usage_metrics=cast(
                dict[str, object], dict(usage) if isinstance(usage, Mapping) else {}
            ),
            message="CrewAI runtime completed.",
        )

    @staticmethod
    def _crewai_module() -> _CrewAIModule:
        try:
            crewai = import_module("crewai")
        except ImportError as exc:
            raise CrewAIConfigurationError(
                "CrewAI is not installed. Install the 'crewai' extra."
            ) from exc
        return cast(_CrewAIModule, crewai)

    @staticmethod
    def _output_model(model_name: str | None) -> type[BaseModel] | None:
        if model_name is None:
            return None
        from ai_software_factory import models

        model = getattr(models, model_name, None)
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise CrewAIConfigurationError(f"Unknown Pydantic output model '{model_name}'.")
        return model


class CrewAIRuntimeFactory:
    def __init__(self, config: CrewAIConfig | None = None) -> None:
        self.config = config

    def create(self, crew_id: str) -> CrewAIRuntime:
        return CrewAIRuntime(self.config)
