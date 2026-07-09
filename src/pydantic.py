# mypy: ignore-errors
import json
from datetime import datetime
from pathlib import Path


class ConfigDict(dict):
    pass


class FieldInfo:
    def __init__(self, default=None, default_factory=None):
        self.default = default
        self.default_factory = default_factory


def Field(default=None, *, default_factory=None):
    return FieldInfo(default, default_factory)


class BaseModel:
    def __init__(self, **data):
        anns = {}
        for cls in reversed(type(self).mro()):
            anns.update(getattr(cls, "__annotations__", {}))
        for k, v in anns.items():
            if k == "model_config":
                continue
            if k in data:
                val = data.pop(k)
            else:
                default = getattr(type(self), k, None)
                if isinstance(default, FieldInfo):
                    val = default.default_factory() if default.default_factory else default.default
                else:
                    val = default
            setattr(self, k, val)
        if data:
            raise TypeError(f"Extra fields {list(data)}")

    @classmethod
    def model_validate(cls, data):
        return cls(**data)

    def model_dump(self):
        return dict(self.__dict__)

    def model_dump_json(self, indent=None):
        def default(o):
            if isinstance(o, Path):
                return str(o)
            if isinstance(o, datetime):
                return o.isoformat()
            if hasattr(o, "value"):
                return o.value
            raise TypeError(type(o).__name__)

        return json.dumps(self.model_dump(), default=default, indent=indent)
