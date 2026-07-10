import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, Self, cast, overload, runtime_checkable

# Lightweight local fallback for environments without pydantic installed.
# Its API boundary intentionally uses Any where it mirrors pydantic's dynamic model data.


@runtime_checkable
class HasValue(Protocol):
    value: object


class ValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self._errors = [{"loc": (field,), "msg": message}]
        super().__init__(message)

    def errors(self) -> list[dict[str, object]]:
        return cast(list[dict[str, object]], self._errors)


class ConfigDict(dict[str, object]):
    pass


class FieldInfo:
    def __init__(
        self, default: object = None, default_factory: Callable[[], object] | None = None
    ) -> None:
        self.default = default
        self.default_factory = default_factory


@overload
def Field[T](default: T, *, default_factory: None = None) -> T: ...


@overload
def Field[T](default: None = None, *, default_factory: Callable[[], T]) -> T: ...


def Field(default: object = None, *, default_factory: Callable[[], object] | None = None) -> Any:
    return FieldInfo(default, default_factory)


class BaseModel:
    def __init__(self, **data: object) -> None:
        anns: dict[str, object] = {}
        for cls in reversed(type(self).mro()):
            cls_annotations = getattr(cls, "__annotations__", {})
            if isinstance(cls_annotations, Mapping):
                anns.update(cls_annotations)
        for key in anns:
            if key == "model_config":
                continue
            if key in data:
                val = data.pop(key)
            else:
                default = getattr(type(self), key, None)
                if isinstance(default, FieldInfo):
                    val = default.default_factory() if default.default_factory else default.default
                else:
                    val = default
            setattr(self, key, val)
        if data:
            raise TypeError(f"Extra fields {list(data)}")

    @classmethod
    def model_validate(cls: type[Self], data: Mapping[str, object]) -> Self:
        return cls(**data)

    def model_dump(self) -> dict[str, object]:
        return dict(self.__dict__)

    def model_dump_json(self, indent: int | None = None) -> str:
        def default(o: object) -> object:
            if isinstance(o, Path):
                return str(o)
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, HasValue):
                return o.value
            raise TypeError(type(o).__name__)

        return json.dumps(self.model_dump(), default=default, indent=indent)
