# Architecture notes

## `src/` layout

The repository uses a `src/` layout so tests import the installed package instead of accidentally importing files from the repository root. This keeps editable installs and packaging behavior close to the way users will consume the project.

## Package responsibilities

- `cli`: Typer commands and command registration.
- `crews`: reserved for future crew definitions; no crew is executable in step 1.
- `models`: reserved for future Pydantic configuration and domain models.
- `services`: reserved for future application services that should stay outside the CLI layer.
- `tools`: reserved for future tools exposed to agents or workflows.
- `workflows`: reserved for future orchestration of multi-step framework operations.

## Framework versus project repositories

AI Software Factory is a generic framework. Project-specific context, requirements, generated documents, and repository analysis results belong in the target project repository, not hard-coded in this framework repository.

## Step 1 boundaries

Step 1 intentionally provides only packaging, a minimal CLI, diagnostics, tests, and documentation. It does not scan repositories, create project documentation, execute CrewAI crews, read complete YAML configuration, call model providers, or generate functional specifications.

## FactoryFlow orchestration

`FactoryFlow` keeps the orchestration in the framework's internal Pydantic models instead of adopting CrewAI Flow as the primary state machine. This preserves the existing persistent `.factory/state/` format, deterministic typed routing, and testable human-validation records while leaving CrewAI crews as execution adapters behind the flow steps. CrewAI Flow can still be introduced later as an adapter if it does not replace the internal workflow models or weaken persistence, idempotence, and transition validation.
