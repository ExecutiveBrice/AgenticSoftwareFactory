import ai_software_factory


def test_package_is_importable() -> None:
    assert ai_software_factory.__name__ == "ai_software_factory"


def test_version_is_available() -> None:
    assert ai_software_factory.__version__
