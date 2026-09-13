from __future__ import annotations

from dataclasses import asdict, dataclass
from random import Random


@dataclass(frozen=True, slots=True)
class Genome:
    speed: float
    metabolism: float
    perception: float
    fertility: float
    curiosity: float
    sociability: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "Genome":
        migrated = dict(data)
        migrated.setdefault("sociability", 0.5)
        return cls(**migrated)


def _bounded(value: float) -> float:
    return min(1.0, max(0.0, value))


def random_genome(rng: Random) -> Genome:
    return Genome(
        speed=rng.uniform(0.25, 0.75),
        metabolism=rng.uniform(0.25, 0.75),
        perception=rng.uniform(0.25, 0.75),
        fertility=rng.uniform(0.25, 0.75),
        curiosity=rng.uniform(0.25, 0.75),
        sociability=rng.uniform(0.25, 0.75),
    )


def mutate_genome(
    parent: Genome,
    rng: Random,
    mutation_rate: float,
    sigma: float,
) -> Genome:
    values: dict[str, float] = {}
    for name, value in parent.to_dict().items():
        if rng.random() < mutation_rate:
            value = _bounded(value + rng.gauss(0.0, sigma))
        values[name] = value
    return Genome.from_dict(values)
