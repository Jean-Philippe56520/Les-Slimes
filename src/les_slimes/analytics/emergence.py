from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Any

from ..world.engine import World


@dataclass(frozen=True, slots=True)
class EmergenceCandidate:
    kind: str
    confidence: float
    summary: str
    evidence: dict[str, Any]


def _trait_summary(world: World) -> dict[str, dict[str, float]]:
    if not world.slimes:
        return {}
    trait_names = tuple(next(iter(world.slimes.values())).genome.to_dict())
    result: dict[str, dict[str, float]] = {}
    for trait in trait_names:
        values = [getattr(slime.genome, trait) for slime in world.slimes.values()]
        result[trait] = {
            "mean": statistics.fmean(values),
            "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }
    return result


def _signal_summary(world: World) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    population = max(1, len(world.slimes))
    for signal in World.SIGNALS:
        values = [
            slime.signal_food_associations.get(signal, 0.0)
            for slime in world.slimes.values()
        ]
        adopters_response = sum(
            1 for value in values if value >= world.config.signal_response_threshold
        )
        adopters_emit = sum(
            1 for value in values if value >= world.config.signal_emit_threshold
        )
        result[signal] = {
            "mean_food_association": statistics.fmean(values) if values else 0.0,
            "max_food_association": max(values, default=0.0),
            "responders": adopters_response,
            "emitters": adopters_emit,
            "responder_fraction": adopters_response / population,
            "emitter_fraction": adopters_emit / population,
        }
    return result


def _social_clusters(world: World, threshold: float = 0.55) -> list[list[str]]:
    ids = sorted(world.slimes)
    parent = {slime_id: slime_id for slime_id in ids}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    for slime in world.slimes.values():
        for target_id, relation in slime.relations.items():
            if target_id in parent and relation.familiarity >= threshold:
                union(slime.id, target_id)

    groups: dict[str, list[str]] = {}
    for slime_id in ids:
        groups.setdefault(find(slime_id), []).append(slime_id)
    clusters = sorted(groups.values(), key=lambda group: (-len(group), group[0]))
    return clusters


def detect_emergence(world: World) -> list[EmergenceCandidate]:
    candidates: list[EmergenceCandidate] = []
    population = len(world.slimes)
    if population == 0:
        return candidates

    signals = _signal_summary(world)
    min_shared = max(3, int(population * 0.10))
    for signal, stats in signals.items():
        emitters = int(stats["emitters"])
        if emitters >= min_shared:
            fraction = float(stats["emitter_fraction"])
            confidence = min(0.95, 0.55 + fraction)
            candidates.append(
                EmergenceCandidate(
                    kind="shared_signal_food",
                    confidence=confidence,
                    summary=(
                        f"{signal} est associé à la nourriture chez {emitters} Slimes "
                        f"({fraction:.1%} de la population)."
                    ),
                    evidence={"signal": signal, **stats},
                )
            )

    clusters = _social_clusters(world, threshold=world.config.social_follow_threshold)
    largest = len(clusters[0]) if clusters else 0
    if largest >= max(5, int(population * 0.15)):
        fraction = largest / population
        candidates.append(
            EmergenceCandidate(
                kind="social_cluster",
                confidence=min(0.9, 0.5 + fraction),
                summary=(
                    f"Un cluster social contient {largest} Slimes "
                    f"({fraction:.1%} de la population)."
                ),
                evidence={
                    "largest_cluster_size": largest,
                    "population": population,
                    "largest_cluster": clusters[0][:50],
                },
            )
        )

    return sorted(candidates, key=lambda item: item.confidence, reverse=True)


def build_world_report(world: World) -> dict[str, Any]:
    metrics = world.metrics()
    clusters = _social_clusters(world, threshold=world.config.social_follow_threshold)
    signals = _signal_summary(world)
    candidates = detect_emergence(world)

    top_social = sorted(
        world.slimes.values(),
        key=lambda slime: (
            sum(rel.familiarity for rel in slime.relations.values()),
            slime.offspring_count,
            slime.id,
        ),
        reverse=True,
    )[:10]

    return {
        "schema_version": "0.3",
        "tick": world.tick,
        "seed": world.config.seed,
        "state_digest": world.state_digest(),
        "metrics": asdict(metrics),
        "traits": _trait_summary(world),
        "signals": signals,
        "social": {
            "cluster_count": len(clusters),
            "largest_cluster_size": len(clusters[0]) if clusters else 0,
            "largest_clusters": [cluster[:25] for cluster in clusters[:5]],
            "top_social_individuals": [
                {
                    "id": slime.id,
                    "relations": len(slime.relations),
                    "familiarity_sum": sum(
                        rel.familiarity for rel in slime.relations.values()
                    ),
                    "offspring": slime.offspring_count,
                }
                for slime in top_social
            ],
        },
        "behavior_rules": [
            rule.to_dict()
            for rule in sorted(world.behavior_rules.values(), key=lambda item: item.id)
        ],
        "mysteries": [
            mystery.public_dict()
            for mystery in sorted(world.mysteries.values(), key=lambda item: item.id)
        ],
        "emergence_candidates": [asdict(candidate) for candidate in candidates],
    }
