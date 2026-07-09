# mypy: ignore-errors
from pathlib import Path


class InvalidGitRepositoryError(Exception):
    pass


class NoSuchPathError(Exception):
    pass


class Repo:
    def __init__(self, path, search_parent_directories=False):
        p = Path(path).resolve()
        cur = p
        while True:
            if (cur / ".git").exists():
                return
            if not search_parent_directories or cur.parent == cur:
                break
            cur = cur.parent
        raise InvalidGitRepositoryError(str(path))
