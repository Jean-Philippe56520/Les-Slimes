from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    sequence: int
    tick: int
    type: str
    subject_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
