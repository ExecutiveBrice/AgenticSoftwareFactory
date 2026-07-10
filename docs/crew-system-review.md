# Crew System Review

## Factual status

The crew system is implemented as a validated MVP. The repository contains strict Pydantic models, repository-bounded artifact services, local identifier generation, a crew registry, YAML crew resources, deterministic fake runtimes for tests, an optional CrewAI adapter, and a persistent `FactoryFlow` stored under `.factory/state/`.

The system is not a full autonomous delivery engine. Base installation does not call LLMs, `factory init` does not generate files, and CrewAI execution requires optional dependencies plus external LLM configuration.

## Seven crews

Each crew has `agents.yaml` and `tasks.yaml` files under `src/ai_software_factory/resources/crews/<crew>/`. The definitions are generic and are validated by tests.

| Crew | Agents | Write area | Verdicts or decisions |
| --- | --- | --- | --- |
| discovery | repository_analyst, business_analyst, requirements_reviewer, discovery_writer | `project/discovery/`, `project/specifications/` | Product Owner approval, rejection, or change request |
| knowledge | project_librarian, documentation_auditor | `project/context.md`, `project/glossary.md`, `project/roadmap.md`, `project/changelog.md`, `project/decisions/`, `project/reviews/KNOWLEDGE/`, `project/reports/knowledge/` | knowledge completion or failure |
| design | solution_architect, domain_designer, ux_designer, security_architect, design_reviewer | `project/architecture/`, `project/design/` | approved, rejected, or changes requested |
| planning | delivery_planner, technical_task_writer, test_planner, dependency_reviewer | `project/backlog/`, `project/planning/` | approved, rejected, or changes requested |
| development | codebase_analyst, software_developer, test_developer, documentation_developer, implementation_reviewer | explicit task paths plus `project/development/` and `project/reviews/DEV/` | development completed or failed |
| qa | qa_analyst, test_executor, regression_analyst, qa_reporter | `project/reviews/QA/`, `project/reports/qa/` | pass, pass with warnings, fail, or blocked |
| review | code_reviewer, architecture_reviewer, security_reviewer, release_reviewer, review_lead | `project/reviews/TECH/`, `project/reports/tech/` | approved, changes requested, rejected, or blocked |

## Routing graph

Discovery starts a request, may suspend for clarification, then waits for Product Owner specification approval. Approval routes to knowledge, design, planning, development, QA, review, knowledge refresh, and final acceptance states as implemented by `FactoryFlow`. QA and review verdicts are routed explicitly by `flows.routing`.

## FakeRuntime for tests

`FakeCrewRuntime` returns deterministic completed task results and records all `CrewRunRequest` values it receives. `FakeCrewRuntimeFactory` creates or reuses fake runtimes per crew. This keeps tests deterministic and avoids CrewAI, network access, or LLM credentials.

## Security

- Artifact writes are bounded to the repository root and path traversal is rejected.
- Each crew has an explicit repository permission policy for create, modify, and delete actions.
- Documentation-oriented crews cannot modify arbitrary target source code.
- Development may write only explicit task paths and development review artifacts.
- Human validation records preserve Product Owner decisions before sensitive transitions.

## Test coverage

The test suite covers Pydantic models, verdict routing, identifier generation, path traversal protection, no-overwrite behavior, crew registry behavior, YAML resource validation, atomic persistence, CLI commands, fake runtimes, and main flow routing.

## Known limits

- `factory init` is present but does not generate initial project files.
- Real LLM calls are not part of the base installation.
- CrewAI execution is optional and depends on external credentials and provider configuration.
- Repository analysis is bounded and read-only by default.
- Development crew behavior is constrained by task paths and is not unrestricted autonomous code editing.
- MVP artifacts should be reviewed by a human Product Owner.
