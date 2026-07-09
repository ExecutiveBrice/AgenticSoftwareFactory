# mypy: ignore-errors
import sys
from pathlib import Path

import typer
from ai_software_factory import __version__
from ai_software_factory.flows import FactoryFlow
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
    typer.echo("Project initialization is not implemented yet. Continue with step 2.")


@app.command("request")
def request(raw_request: str) -> None:
    state = FactoryFlow(Path.cwd()).start_request(raw_request)
    typer.echo(state.request_id)


@app.command("status")
def status(request_id: str) -> None:
    state = FactoryFlow(Path.cwd()).resume(request_id)
    typer.echo(f"{state.request_id}: {state.status}")


@app.command("resume")
def resume(request_id: str) -> None:
    status(request_id)


@app.command("approve")
def approve(request_id: str) -> None:
    typer.echo(f"Approval recorded for {request_id}; orchestration resume is MVP-only.")


@app.command("reject")
def reject(request_id: str) -> None:
    typer.echo(f"Rejection recorded for {request_id}; orchestration resume is MVP-only.")


@app.command("answer")
def answer(request_id: str, answer_text: str) -> None:
    typer.echo(f"Answer recorded for {request_id}: {answer_text}")
