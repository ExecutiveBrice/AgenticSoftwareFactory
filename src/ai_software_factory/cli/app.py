import sys
from pathlib import Path

import typer
from ai_software_factory import __version__
from ai_software_factory.flows import FactoryFlow
from ai_software_factory.models import DiscoveryVerdict
from ai_software_factory.workflows import DiscoveryWorkflow
from git import InvalidGitRepositoryError, NoSuchPathError, Repo

app = typer.Typer(
    name="factory", help="AI Software Factory command-line interface.", no_args_is_help=True
)


def _status_line(label: str, status: str) -> str:
    width = 26 if label == "Git repository" else 25
    return f"{label:.<{width}} {status}"


def _is_git_repository(path: Path) -> bool:
    try:
        Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return False
    return True


@app.command()
def version() -> None:
    typer.echo(f"AI Software Factory {__version__}")


@app.command()
def doctor() -> None:
    cwd = Path.cwd()
    typer.echo(_status_line("Python 3.12+", "OK" if sys.version_info >= (3, 12) else "UNSUPPORTED"))
    typer.echo(_status_line("Git repository", "OK" if _is_git_repository(cwd) else "MISSING"))
    typer.echo(
        _status_line(".factory.yaml", "OK" if (cwd / ".factory.yaml").is_file() else "MISSING")
    )
    typer.echo(
        _status_line("project/ directory", "OK" if (cwd / "project").is_dir() else "MISSING")
    )


@app.command("init")
def init_project() -> None:
    typer.echo(
        "Project initialization is not automated yet; "
        "create .factory.yaml and project/ manually when needed."
    )


@app.command("request")
def request(raw_request: str) -> None:
    state = FactoryFlow(Path.cwd()).start_request(raw_request)
    typer.echo(state.request_id)


@app.command("status")
def status(request_id: str) -> None:
    state = FactoryFlow(Path.cwd()).status(request_id)
    typer.echo(f"{state.request_id}: {state.status}")
    for human_request in state.human_requests:
        if human_request.status == "PENDING":
            typer.echo(f"pending {human_request.id}: {human_request.type} {human_request.stage}")


@app.command("resume")
def resume(request_id: str) -> None:
    state = FactoryFlow(Path.cwd()).resume(request_id)
    typer.echo(f"{state.request_id}: {state.status}")


@app.command("approve")
def approve(request_id: str, human_request_id: str | None = None) -> None:
    state = FactoryFlow(Path.cwd()).approve(request_id, human_request_id=human_request_id)
    typer.echo(f"{state.request_id}: {state.status}")


@app.command("reject")
def reject(request_id: str, human_request_id: str | None = None) -> None:
    state = FactoryFlow(Path.cwd()).reject(request_id, human_request_id=human_request_id)
    typer.echo(f"{state.request_id}: {state.status}")


@app.command("answer")
def answer(request_id: str, answer_text: str, human_request_id: str | None = None) -> None:
    state = FactoryFlow(Path.cwd()).answer(
        request_id, answer_text, human_request_id=human_request_id
    )
    typer.echo(f"{state.request_id}: {state.status}")


@app.command("discovery")
def discovery(raw_request: str, repository_path: Path | None = None) -> None:
    target = repository_path or Path.cwd()
    result = DiscoveryWorkflow(target).start(raw_request)
    typer.echo(f"{result.state.request_id} {result.state.feature_id} {result.state.status}")


@app.command("discovery-answer")
def discovery_answer(
    request_id: str, answer_text: str, repository_path: Path | None = None
) -> None:
    target = repository_path or Path.cwd()
    result = DiscoveryWorkflow(target).resume_with_answers(request_id, answer_text)
    typer.echo(f"{result.state.request_id} {result.state.status}")


@app.command("discovery-decision")
def discovery_decision(
    request_id: str, verdict: DiscoveryVerdict, repository_path: Path | None = None
) -> None:
    target = repository_path or Path.cwd()
    state = DiscoveryWorkflow(target).record_product_owner_decision(request_id, verdict)
    typer.echo(f"{state.request_id} {state.status}")
