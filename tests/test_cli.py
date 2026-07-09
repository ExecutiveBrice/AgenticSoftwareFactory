import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_software_factory import __version__
from ai_software_factory.cli.app import app

runner = CliRunner()


def test_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "AI Software Factory command-line interface" in result.output


def test_python_module_help_uses_same_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ai_software_factory", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "AI Software Factory command-line interface" in result.stdout


def test_unknown_command_returns_cli_error() -> None:
    result = runner.invoke(app, ["unknown"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"AI Software Factory {__version__}"


def test_doctor_without_project_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Python 3.12+" in result.output
    assert "Git repository" in result.output
    assert "MISSING" in result.output
    assert ".factory.yaml" in result.output
    assert "project/ directory" in result.output


def test_doctor_detects_git_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Git repository" in result.output
    assert "Git repository............ OK" in result.output


def test_doctor_detects_factory_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".factory.yaml").write_text("# placeholder\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert ".factory.yaml............ OK" in result.output


def test_doctor_detects_project_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "project").mkdir()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "project/ directory....... OK" in result.output


def test_init_placeholder_has_no_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = set(tmp_path.iterdir())
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    after = set(tmp_path.iterdir())
    assert result.exit_code == 0
    assert (
        result.output.strip()
        == "Project initialization is not implemented yet. Continue with step 2."
    )
    assert after == before
