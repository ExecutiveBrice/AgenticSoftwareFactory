# AI Software Factory

AI Software Factory is a generic framework for orchestrating AI agent teams that support software delivery while keeping the human user in the Product Owner role.

## Current status

The repository currently provides an installable Python package, a Typer-based CLI, a persistent MVP workflow stored under `.factory/state/`, validated crew definitions loaded from YAML resources, repository-bounded artifact services, deterministic test runtimes, and an optional CrewAI adapter.

Operational today:

- CLI diagnostics with `factory doctor`.
- Request lifecycle commands: `factory request`, `factory status`, `factory answer`, `factory approve`, `factory reject`, and `factory resume`.
- Discovery workflow commands: `factory discovery`, `factory discovery-answer`, and `factory discovery-decision`.
- Seven validated crew definitions: discovery, knowledge, design, planning, development, QA, and review.
- Deterministic `FakeCrewRuntime` used by tests and by code paths that need runtime behavior without external services.

Partial or not yet complete:

- `factory init` is a compatibility command and currently reports that project initialization is not yet automated; create `.factory.yaml` and `project/` manually when needed.
- CrewAI integration is available through the optional adapter, but it requires optional dependencies and external LLM configuration.
- The flow persists and routes state, but end-to-end autonomous implementation of target repository code is not provided.

## Prerequisites

- Python 3.12 or newer
- Git
- `pip`

## Installation

Base installation for CLI, models, YAML validation, and deterministic tests:

```bash
python -m pip install -e ".[dev]"
```

Installation with the optional CrewAI adapter:

```bash
python -m pip install -e ".[dev,crewai]"
```

## LLM configuration

The base installation does not call an LLM. To run crews through CrewAI, install the `crewai` extra and configure credentials supported by your CrewAI/LLM environment before invoking runtime code that uses `CrewAIRuntimeFactory`. Tests use `FakeCrewRuntime`, so no LLM credentials are required for the default test suite.

## CLI reference

The installed console script is `factory`. In an editable checkout without console scripts on `PATH`, the same application can be invoked with `python -m ai_software_factory` when `src` is importable.

```bash
factory --help
factory version
factory doctor
factory init
factory request "Describe the desired change generically."
factory status REQ-001
factory answer REQ-001 "Clarification response" [HUMAN-REQUEST-ID]
factory approve REQ-001 [HUMAN-REQUEST-ID]
factory reject REQ-001 [HUMAN-REQUEST-ID]
factory resume REQ-001
factory discovery "Describe the desired change generically."
factory discovery-answer REQ-001 "Clarification response"
factory discovery-decision REQ-001 approve
python -m ai_software_factory --help
```

### `factory init`

Reports that automated project initialization is not yet implemented. It intentionally has no filesystem side effects in the current version.

### `factory doctor`

Checks the current directory for:

- Python 3.12+;
- a Git repository;
- `.factory.yaml`;
- a `project/` directory.

### `factory request`

Starts a persisted workflow request from free text and prints the generated request identifier.

### `factory status`

Loads the persisted workflow state and prints the current status. Pending human validation requests are listed when present.

### `factory answer`

Records a Product Owner clarification answer for a pending human request. The human request id is optional when there is only one pending request.

### `factory approve`

Approves a pending human validation request and advances the flow according to the current stage.

### `factory reject`

Rejects a pending human validation request and records the corresponding state transition.

### `factory resume`

Reloads a persisted request and continues deterministic routing where the current state allows it.

## Complete generic example

```bash
# 1. Prepare a repository workspace.
git init
mkdir -p project
printf "# AI Software Factory configuration\n" > .factory.yaml

# 2. Inspect readiness.
factory doctor

# 3. Automated initialization is not yet available, but the command is present.
factory init

# 4. Submit a request.
REQUEST_ID=$(factory request "Create a small, generic improvement with clear acceptance criteria.")

# 5. Inspect state and any pending Product Owner request.
factory status "$REQUEST_ID"

# 6. Answer a clarification if one is pending.
factory answer "$REQUEST_ID" "Keep the scope minimal and preserve current behavior."

# 7. Approve the generated specification when the flow requests approval.
factory approve "$REQUEST_ID"

# 8. Consult the final or next state.
factory status "$REQUEST_ID"
```

## Main tree

```text
src/ai_software_factory/           Python package
src/ai_software_factory/cli/       Typer CLI and command registration
src/ai_software_factory/crews/     Crew abstractions, registry, runtime adapters
src/ai_software_factory/flows/     Persistent workflow state and routing
src/ai_software_factory/models/    Strict Pydantic models and verdicts
src/ai_software_factory/services/  Artifact, identifier, and repository policy services
src/ai_software_factory/tools/     Read-only repository tools
src/ai_software_factory/workflows/ Discovery workflow orchestration
tests/                             Unit and integration-style tests
docs/                              Project documentation
templates/                         Template location
examples/                          Example location
```

## Crews, write areas, and verdicts

| Crew | Main role | Write area | Verdicts or decisions |
| --- | --- | --- | --- |
| discovery | Analyze a request and prepare discovery/specification artifacts. | `project/discovery/`, `project/specifications/` | discovery approval, rejection, or change request through Product Owner decisions |
| knowledge | Maintain project knowledge from accepted artifacts. | `project/context.md`, `project/glossary.md`, `project/roadmap.md`, `project/changelog.md`, `project/decisions/`, `project/reviews/KNOWLEDGE/`, `project/reports/knowledge/` | knowledge completion/failure |
| design | Produce solution design artifacts. | `project/architecture/`, `project/design/` | design approved, rejected, or changes requested |
| planning | Convert approved design into delivery work. | `project/backlog/`, `project/planning/` | planning approved, rejected, or changes requested |
| development | Execute approved tasks within explicitly allowed paths. | Task-specific paths plus `project/development/` and `project/reviews/DEV/` | development completed or failed |
| qa | Evaluate development outputs. | `project/reviews/QA/`, `project/reports/qa/` | pass, pass with warnings, fail, or blocked |
| review | Perform final technical review. | `project/reviews/TECH/`, `project/reports/tech/` | approved, changes requested, rejected, or blocked |

## Security

- Artifact writes are resolved inside the repository and protected against path traversal.
- Crew write permissions are expressed as repository policies per crew.
- Most crews are documentation/artifact oriented and do not modify target source code.
- Development writes are limited to explicit task paths and development review artifacts.
- Default tests and `FakeCrewRuntime` do not call external services.

## Known limits

- Automated `factory init` file generation is not implemented.
- CrewAI execution requires optional dependencies and external LLM credentials.
- Repository analysis is intentionally bounded and not a complete semantic understanding of every file.
- Autonomous target-code modification is limited by explicit task paths and is not an unrestricted coding agent.
- Generated artifacts are MVP outputs and should be reviewed by the Product Owner.

## FakeRuntime for tests

`FakeCrewRuntime` and `FakeCrewRuntimeFactory` provide deterministic crew outputs, record runtime requests, and avoid external services. They are the default tools for tests that exercise crew orchestration without CrewAI or LLM credentials.

## Quality commands

```bash
pytest
ruff check .
ruff format --check .
mypy src
```
