from __future__ import annotations

from dataclasses import dataclass
from math import exp, hypot


@dataclass(slots=True)
class FoodMemory:
    x: float
    y: float
    strength: float
    last_seen_tick: int

    def score(self, tick: int, decay: float) -> float:
        age = max(0, tick - self.last_seen_tick)
        return self.strength * exp(-decay * age)


def remember_food(
    memories: list[FoodMemory],
    *,
    x: float,
    y: float,
    tick: int,
    strength: float,
    merge_radius: float,
    capacity: int,
    decay: float,
) -> None:
    closest: FoodMemory | None = None
    closest_distance = float("inf")
    for memory in memories:
        distance = hypot(memory.x - x, memory.y - y)
        if distance < closest_distance:
            closest = memory
            closest_distance = distance

    if closest is not None and closest_distance <= merge_radius:
        closest.x = (closest.x + x) / 2.0
        closest.y = (closest.y + y) / 2.0
        closest.strength = min(1.0, max(closest.strength, strength) + 0.08)
        closest.last_seen_tick = tick
    else:
        memories.append(FoodMemory(x=x, y=y, strength=min(1.0, strength), last_seen_tick=tick))

    if len(memories) > capacity:
        memories.sort(key=lambda m: m.score(tick, decay), reverse=True)
        del memories[capacity:]


def best_food_memory(
    memories: list[FoodMemory], tick: int, decay: float
) -> FoodMemory | None:
    if not memories:
        return None
    memory = max(memories, key=lambda m: m.score(tick, decay))
    return memory if memory.score(tick, decay) >= 0.08 else None
