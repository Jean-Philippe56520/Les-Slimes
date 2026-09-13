from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class WorldConfig:
    seed: int = 428719
    width: float = 120.0
    height: float = 80.0
    initial_slimes: int = 100
    initial_food: int = 180
    max_food: int = 260
    food_spawn_probability: float = 0.15
    food_nutrition: float = 28.0
    forage_energy_threshold: float = 78.0
    eat_energy_threshold: float = 92.0
    max_energy: float = 100.0
    initial_energy: float = 62.0
    birth_energy: float = 36.0
    reproduction_energy_threshold: float = 78.0
    reproduction_energy_cost: float = 38.0
    maturity_age_ticks: int = 800
    reproduction_cooldown_ticks: int = 700
    base_reproduction_probability: float = 0.00020
    base_max_age_ticks: int = 18000
    founder_age_max_fraction: float = 0.35
    base_metabolic_cost: float = 0.020
    move_energy_cost: float = 0.012
    eat_radius: float = 1.3
    memory_decay: float = 0.0008
    memory_merge_radius: float = 3.0
    mutation_rate: float = 0.12
    mutation_sigma: float = 0.07
    low_energy_health_threshold: float = 8.0
    low_energy_health_loss: float = 0.12
    health_recovery: float = 0.02
    checkpoint_interval: int = 250
    social_interaction_radius: float = 3.0
    social_update_interval: int = 10
    social_learning_rate: float = 0.035
    social_follow_threshold: float = 0.55
    social_follow_radius: float = 10.0
    max_relations_per_slime: int = 24
    signal_radius: float = 12.0
    signal_association_window: int = 90
    signal_learning_rate: float = 0.22
    signal_extinction_rate: float = 0.04
    signal_response_threshold: float = 0.35
    signal_emit_threshold: float = 0.55
    signal_emit_probability: float = 0.004
    signal_emit_cooldown: int = 80
    mystery_trigger_cooldown: int = 120

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("World dimensions must be positive")
        if self.initial_slimes < 1:
            raise ValueError("initial_slimes must be >= 1")
        if self.initial_food < 0 or self.max_food < self.initial_food:
            raise ValueError("Food counts are inconsistent")
        if not 0.0 <= self.food_spawn_probability <= 1.0:
            raise ValueError("food_spawn_probability must be in [0, 1]")
        if self.max_energy <= 0 or self.initial_energy <= 0:
            raise ValueError("Energy values must be positive")
        if not 0 < self.forage_energy_threshold <= self.eat_energy_threshold <= self.max_energy:
            raise ValueError("Energy thresholds must satisfy 0 < forage <= eat <= max_energy")
        if not 0.0 <= self.founder_age_max_fraction < 1.0:
            raise ValueError("founder_age_max_fraction must be in [0, 1)")
        if self.checkpoint_interval < 1:
            raise ValueError("checkpoint_interval must be >= 1")
        if self.social_update_interval < 1:
            raise ValueError("social_update_interval must be >= 1")
        if self.max_relations_per_slime < 1:
            raise ValueError("max_relations_per_slime must be >= 1")
        if self.social_interaction_radius <= 0 or self.signal_radius <= 0:
            raise ValueError("Social/signal radii must be positive")
        if self.signal_association_window < 1 or self.signal_emit_cooldown < 1:
            raise ValueError("Signal timing values must be positive")
        if self.mystery_trigger_cooldown < 1:
            raise ValueError("mystery_trigger_cooldown must be positive")
        for value in (
            self.social_learning_rate,
            self.social_follow_threshold,
            self.signal_learning_rate,
            self.signal_extinction_rate,
            self.signal_response_threshold,
            self.signal_emit_threshold,
            self.signal_emit_probability,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("Learning/probability thresholds must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldConfig":
        cfg = cls(**data)
        cfg.validate()
        return cfg

    @classmethod
    def from_yaml(cls, path: str | Path) -> "WorldConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        if not isinstance(raw, dict):
            raise ValueError("Configuration root must be a mapping")
        return cls.from_dict(raw)
