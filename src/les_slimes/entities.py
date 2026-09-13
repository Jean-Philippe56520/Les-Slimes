from __future__ import annotations

from dataclasses import dataclass, field

from .biology.genetics import Genome
from .cognition.memory import FoodMemory


@dataclass(slots=True)
class Food:
    id: int
    x: float
    y: float
    nutrition: float


@dataclass(slots=True)
class Relation:
    familiarity: float = 0.0
    trust: float = 0.0
    interactions: int = 0
    last_interaction_tick: int = 0


@dataclass(slots=True)
class HeardSignal:
    signal: str
    x: float
    y: float
    tick: int
    source_id: str | None = None


@dataclass(slots=True)
class Slime:
    id: str
    parent_id: str | None
    generation: int
    x: float
    y: float
    heading: float
    energy: float
    health: float
    age_ticks: int
    born_tick: int
    last_reproduction_tick: int
    genome: Genome
    memories: list[FoodMemory] = field(default_factory=list)
    relations: dict[str, Relation] = field(default_factory=dict)
    signal_food_associations: dict[str, float] = field(default_factory=dict)
    heard_signals: list[HeardSignal] = field(default_factory=list)
    last_signal_emit_tick: int = -1_000_000
    distance_travelled: float = 0.0
    food_eaten: int = 0
    offspring_count: int = 0
    current_action: str = "idle"
    alive: bool = True

    @property
    def memory_capacity(self) -> int:
        return 3 + int(self.genome.curiosity * 9)
