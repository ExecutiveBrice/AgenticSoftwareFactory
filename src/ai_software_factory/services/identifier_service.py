# mypy: ignore-errors
import re
from pathlib import Path


class IdentifierService:
    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path
        self.reserved: set[str] = set()

    def _seen(self, prefix: str) -> set[int]:
        pat = re.compile(rf"\b{re.escape(prefix)}-(\d{{4}})\b")
        seen = {
            int(m.group(1))
            for p in self.repository_path.rglob("*")
            if p.is_file()
            for m in pat.finditer(str(p.relative_to(self.repository_path)))
        }
        seen |= {
            int(x.split("-")[1])
            for x in self.reserved
            if x.startswith(prefix + "-") and len(x.split("-")) >= 2
        }
        return seen

    def next(self, prefix: str) -> str:
        n = 1
        seen = self._seen(prefix)
        while n in seen:
            n += 1
        ident = f"{prefix}-{n:04d}"
        self.reserved.add(ident)
        return ident

    def request_id(self) -> str:
        return self.next("REQ")

    def feature_id(self) -> str:
        return self.next("FEAT")

    def decision_id(self) -> str:
        return self.next("DEC")

    def epic_id(self) -> str:
        return self.next("EPIC")

    def task_id(self, feature_number: int, sequence: int) -> str:
        ident = f"TASK-{feature_number:04d}-{sequence:02d}"
        self.reserved.add(ident)
        return ident
