# Architecture notes

## `src/` layout

The repository uses a `src/` layout so tests import the installed package instead of accidentally importing files from the repository root. This keeps editable installs and packaging behavior close to the way users consume the project.

## Package responsibilities

- `cli`: Typer command registration for diagnostics, request lifecycle commands, and discovery workflow commands.
- `crews`: crew definitions, registry, base execution wrapper, runtime protocol, deterministic fake runtime, disabled runtime, and optional CrewAI runtime adapter.
- `flows`: persistent workflow state, atomic state storage, human validation records, transition validation, and verdict routing.
- `models`: strict Pydantic models for configuration, crews, artifacts, workflow state, human validation, and verdicts.
- `services`: repository-bounded artifact writes, local identifier generation, and per-crew repository permission policies.
- `tools`: read-only repository inspection utilities.
- `workflows`: higher-level orchestration, currently focused on discovery.

## Framework versus project repositories

AI Software Factory is a generic framework. Project-specific context, requirements, generated documents, repository analysis results, and workflow state belong in the target project repository. The framework must not hard-code business domains, target languages, or target frameworks.

## Operational boundaries

The current implementation provides validated crew YAML resources, deterministic flow routing, persisted `.factory/state/` records, bounded artifact services, and CLI commands for the request lifecycle. It does not provide fully automated project initialization, unrestricted source-code modification, or default LLM execution in the base installation.

## CLI architecture

The public CLI is exposed as `factory` and through `python -m ai_software_factory`. The documented commands are synchronized with `factory --help`:

- `version`
- `doctor`
- `init`
- `request`
- `status`
- `resume`
- `approve`
- `reject`
- `answer`
- `discovery`
- `discovery-answer`
- `discovery-decision`

`request`, `status`, `resume`, `approve`, `reject`, and `answer` use `FactoryFlow`. The discovery-specific commands use `DiscoveryWorkflow`.

## FactoryFlow orchestration

`FactoryFlow` keeps orchestration in the framework's internal Pydantic models instead of adopting CrewAI Flow as the primary state machine. This preserves the persistent `.factory/state/` format, deterministic typed routing, and testable human-validation records while leaving CrewAI crews as execution adapters behind the flow steps. CrewAI Flow can still be introduced later as an adapter if it does not replace the internal workflow models or weaken persistence, idempotence, and transition validation.

## Crew system

Seven crews are defined through YAML resources under `src/ai_software_factory/resources/crews/<crew>/` and loaded through validation code:

| Crew | Agents | Write area | Verdicts or decisions |
| --- | --- | --- | --- |
| discovery | repository_analyst, business_analyst, requirements_reviewer, discovery_writer | `project/discovery/`, `project/specifications/` | Product Owner approval, rejection, or change request for discovery/specification output |
| knowledge | project_librarian, documentation_auditor | `project/context.md`, `project/glossary.md`, `project/roadmap.md`, `project/changelog.md`, `project/decisions/`, `project/reviews/KNOWLEDGE/`, `project/reports/knowledge/` | completion/failure of knowledge artifacts |
| design | solution_architect, domain_designer, ux_designer, security_architect, design_reviewer | `project/architecture/`, `project/design/` | approved, rejected, or changes requested |
| planning | delivery_planner, technical_task_writer, test_planner, dependency_reviewer | `project/backlog/`, `project/planning/` | approved, rejected, or changes requested |
| development | codebase_analyst, software_developer, test_developer, documentation_developer, implementation_reviewer | explicit task paths, `project/development/`, `project/reviews/DEV/` | completed or failed |
| qa | qa_analyst, test_executor, regression_analyst, qa_reporter | `project/reviews/QA/`, `project/reports/qa/` | pass, pass with warnings, fail, or blocked |
| review | code_reviewer, architecture_reviewer, security_reviewer, release_reviewer, review_lead | `project/reviews/TECH/`, `project/reports/tech/` | approved, changes requested, rejected, or blocked |

## Runtime adapters

- `FakeCrewRuntime` returns deterministic task outputs, records requests, and avoids external dependencies. It is used by tests and by deterministic orchestration scenarios.
- `DisabledCrewRuntime` returns a typed failure when real crew execution is unavailable.
- `CrewAIRuntime` adapts validated crew definitions to CrewAI `Agent`, `Task`, `Crew`, and sequential `Process` APIs when the optional dependency and LLM environment are configured.

## Security

- Artifact paths are resolved under the repository root and path traversal is rejected.
- Repository permission policies restrict each crew's read, create, modify, and delete areas.
- Development delete permissions are limited to explicit task paths.
- The default test/runtime path does not require network calls or LLM credentials.
- Human approval records are persisted before the flow advances through approval-sensitive stages.

## Known limits

- `factory init` currently reports status only and does not generate `.factory.yaml` or `project/`.
- CrewAI integration is optional and depends on external configuration.
- The MVP flow emphasizes state, validation, and artifacts rather than complete autonomous delivery.
- Repository inspection tools are intentionally read-only and bounded.
