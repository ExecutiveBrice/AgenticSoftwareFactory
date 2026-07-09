# AI Software Factory

AI Software Factory is intended to become a generic framework for orchestrating AI agent teams that support software delivery while keeping the human user in the Product Owner role.

## Current status

This repository is at **step 1: technical foundation**. It provides a minimal, installable, tested Python package and CLI. It does not run crews, scan repositories, call LLMs, or generate project documentation yet.

## Prerequisites

- Python 3.12 or newer
- Git
- `pip`

## Local installation

```bash
python -m pip install -e ".[dev]"
```

## Available commands

```bash
factory --help
factory version
factory doctor
factory init
python -m ai_software_factory --help
```

`factory init` is currently a placeholder and intentionally creates no files.

## Quality commands

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

## Main tree

```text
src/ai_software_factory/  Python package
src/ai_software_factory/cli/  Typer CLI
src/ai_software_factory/crews/  Reserved for future crew definitions
src/ai_software_factory/models/  Reserved for future Pydantic models
src/ai_software_factory/services/  Reserved for future application services
src/ai_software_factory/tools/  Reserved for future agent tools
src/ai_software_factory/workflows/  Reserved for future orchestration workflows
tests/  Unit tests
docs/  Project documentation
templates/  Reserved for future templates
examples/  Reserved for future examples
```

## Intentionally not implemented

The following capabilities are out of scope for step 1:

- full `factory init` behavior;
- repository scanning;
- feature, design, planning, development, QA, or review commands;
- CrewAI execution;
- YAML agents or tasks;
- LLM provider integration;
- functional specification generation;
- automatic modification of target project code.

## Next steps

Step 2 should add the Pydantic configuration model, generate `.factory.yaml`, create the target `project/` documentation directory, and replace the `factory init` placeholder with real initialization behavior.
