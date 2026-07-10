import os
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
os.environ["PYTHONPATH"] = _SRC + os.pathsep + os.environ.get("PYTHONPATH", "")
