from pathlib import Path

import ai_software_factory


def test_package_is_importable() -> None:
    assert ai_software_factory.__name__ == "ai_software_factory"


def test_version_is_available() -> None:
    assert ai_software_factory.__version__


def test_src_has_no_mypy_ignore_errors() -> None:
    src_root = Path(__file__).resolve().parents[1] / "src"

    offenders = sorted(
        path.relative_to(src_root).as_posix()
        for path in src_root.rglob("*.py")
        if "# mypy: ignore-errors" in path.read_text(encoding="utf-8")
    )

    assert offenders == []
