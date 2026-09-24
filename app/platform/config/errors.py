from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfigValidationError(Exception):
    fields: list[str]
    reason: str
    source_file: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", sorted(list(self.fields or [])))

    @property
    def message(self) -> str:
        return f"ConfigValidationError fields={','.join(self.fields)} reason={self.reason} source={self.source_file}"

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": list(self.fields),
            "reason": self.reason,
            "source_file": self.source_file,
            "message": self.message,
        }
