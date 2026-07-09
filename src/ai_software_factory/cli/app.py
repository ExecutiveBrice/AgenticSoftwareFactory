import sys
from pathlib import Path

import typer
from git import InvalidGitRepositoryError, NoSuchPathError, Repo

from ai_software_factory import __version__

app = typer.Typer(
    name="factory",
    help="AI Software Factory command-line interface.",
    no_args_is_help=True,
)


def _status_line(label: str, status: str) -> str:
    return f"{label:.<26} {status}"


def _is_git_repository(path: Path) -> bool:
    try:
        Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return False
    return True


@app.command()
def version() -> None:
    """Display the installed AI Software Factory version."""
    typer.echo(f"AI Software Factory {__version__}")


@app.command()
def doctor() -> None:
    """Run minimal diagnostics for the current working directory."""
    cwd = Path.cwd()
    python_status = "OK" if sys.version_info >= (3, 12) else "UNSUPPORTED"
    git_status = "OK" if _is_git_repository(cwd) else "MISSING"
    config_status = "OK" if (cwd / ".factory.yaml").is_file() else "MISSING"
    project_status = "OK" if (cwd / "project").is_dir() else "MISSING"

    typer.echo(_status_line("Python 3.12+", python_status))
    typer.echo(_status_line("Git repository", git_status))
    typer.echo(_status_line(".factory.yaml", config_status))
    typer.echo(_status_line("project/ directory", project_status))


@app.command("init")
def init_project() -> None:
    """Placeholder for the future project initialization command."""
    typer.echo("Project initialization is not implemented yet. Continue with step 2.")
