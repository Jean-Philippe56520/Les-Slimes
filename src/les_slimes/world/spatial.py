from __future__ import annotations

from collections import defaultdict
from math import floor, hypot

from ..entities import Food


class SpatialFoodIndex:
    def __init__(self, cell_size: float = 8.0) -> None:
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], set[int]] = defaultdict(set)

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return floor(x / self.cell_size), floor(y / self.cell_size)

    def add(self, food: Food) -> None:
        self._cells[self._cell(food.x, food.y)].add(food.id)

    def remove(self, food: Food) -> None:
        cell = self._cell(food.x, food.y)
        ids = self._cells.get(cell)
        if not ids:
            return
        ids.discard(food.id)
        if not ids:
            self._cells.pop(cell, None)

    def nearest(
        self,
        foods: dict[int, Food],
        x: float,
        y: float,
        radius: float,
    ) -> tuple[Food | None, float]:
        min_cx = floor((x - radius) / self.cell_size)
        max_cx = floor((x + radius) / self.cell_size)
        min_cy = floor((y - radius) / self.cell_size)
        max_cy = floor((y + radius) / self.cell_size)

        best: Food | None = None
        best_distance = float("inf")
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                for food_id in self._cells.get((cx, cy), ()):
                    food = foods.get(food_id)
                    if food is None:
                        continue
                    distance = hypot(food.x - x, food.y - y)
                    if distance <= radius and (
                        distance < best_distance
                        or (distance == best_distance and best is not None and food.id < best.id)
                    ):
                        best = food
                        best_distance = distance
        return best, best_distance


class SpatialSlimeIndex:
    def __init__(self, cell_size: float = 6.0) -> None:
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], set[str]] = defaultdict(set)
        self._positions: dict[str, tuple[float, float]] = {}

    def add(self, slime_id: str, x: float, y: float) -> None:
        self._positions[slime_id] = (x, y)
        self._cells[self._cell(x, y)].add(slime_id)

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return floor(x / self.cell_size), floor(y / self.cell_size)

    def neighbors(self, x: float, y: float, radius: float) -> list[tuple[str, float]]:
        min_cx = floor((x - radius) / self.cell_size)
        max_cx = floor((x + radius) / self.cell_size)
        min_cy = floor((y - radius) / self.cell_size)
        max_cy = floor((y + radius) / self.cell_size)
        found: list[tuple[str, float]] = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                for slime_id in self._cells.get((cx, cy), ()):
                    sx, sy = self._positions[slime_id]
                    distance = hypot(sx - x, sy - y)
                    if distance <= radius:
                        found.append((slime_id, distance))
        found.sort(key=lambda item: (item[1], item[0]))
        return found
