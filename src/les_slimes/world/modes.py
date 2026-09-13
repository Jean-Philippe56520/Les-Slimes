from __future__ import annotations

from enum import StrEnum


class WorldMode(StrEnum):
    SANDBOX = "sandbox"
    OBSERVATION = "observation"
    EXPERIMENT = "experiment"

    @classmethod
    def parse(cls, value: str | "WorldMode") -> "WorldMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"Unknown world mode {value!r}; expected {allowed}") from exc
