import subprocess
import sys
from pathlib import Path

import pytest

from ai_software_factory import __version__
from ai_software_factory.cli.app import app
from typer.testing import CliRunner

runner = CliRunner()


def test_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "AI Software Factory command-line interface" in result.output


def test_help_lists_documented_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    commands = [
        "version",
        "doctor",
        "init",
        "request",
        "status",
        "resume",
        "approve",
        "reject",
        "answer",
        "discovery",
        "discovery-answer",
        "discovery-decision",
    ]
    for command in commands:
        assert command in result.output


def test_documented_commands_exist_and_no_unknown_commands_are_documented() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    documented = {
        word
        for line in readme.splitlines()
        if line.startswith("factory ")
        for word in [line.split()[1].strip()]
        if word != "--help"
    }
    expected = {
        "version",
        "doctor",
        "init",
        "request",
        "status",
        "answer",
        "approve",
        "reject",
        "resume",
        "discovery",
        "discovery-answer",
        "discovery-decision",
    }

    assert documented == expected
    command_arguments = {
        "version": [],
        "doctor": [],
        "init": [],
        "request": ["Generic request"],
        "status": ["REQ-001"],
        "answer": ["REQ-001", "Generic answer"],
        "approve": ["REQ-001"],
        "reject": ["REQ-001"],
        "resume": ["REQ-001"],
        "discovery": ["Generic request"],
        "discovery-answer": ["REQ-001", "Generic answer"],
        "discovery-decision": ["REQ-001", "approve"],
    }
    for command in documented:
        assert command in command_arguments


def test_documentation_does_not_claim_yaml_resources_are_missing() -> None:
    for path in [
        Path("README.md"),
        Path("docs/architecture.md"),
        Path("docs/crew-system-review.md"),
    ]:
        text = path.read_text(encoding="utf-8").lower()
        assert "yaml agents or tasks" not in text
        assert "yaml are absent" not in text
        assert "yaml resources are absent" not in text


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


def test_init_reports_current_boundary_and_has_no_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = set(tmp_path.iterdir())
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    after = set(tmp_path.iterdir())
    assert result.exit_code == 0
    assert result.output.strip() == (
        "Project initialization is not automated yet; "
        "create .factory.yaml and project/ manually when needed."
    )
    assert after == before
