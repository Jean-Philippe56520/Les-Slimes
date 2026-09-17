from __future__ import annotations

import hashlib
import json
import math
import pickle
import random
from dataclasses import dataclass
from typing import Iterable

from ..biology.genetics import mutate_genome, random_genome
from ..cognition.memory import best_food_memory, remember_food
from ..cognition.rules import BehaviorRule, rule_matches, validate_rule_payload
from ..config import WorldConfig
from ..entities import Food, HeardSignal, Relation, Slime
from ..events import Event
from .mysteries import MysteryObject, validate_mystery_payload
from .spatial import SpatialFoodIndex, SpatialSlimeIndex


@dataclass(frozen=True, slots=True)
class WorldMetrics:
    tick: int
    population: int
    food_count: int
    births: int
    deaths: int
    mean_energy: float
    mean_health: float
    max_generation: int


class World:
    SIGNALS = ("S1", "S2", "S3", "S4")

    def __init__(
        self,
        config: WorldConfig,
        *,
        initialize: bool = True,
    ) -> None:
        config.validate()
        self.config = config
        self.rng = random.Random(config.seed)
        self.tick = 0
        self.slimes: dict[str, Slime] = {}
        self.foods: dict[int, Food] = {}
        self.next_slime_number = 1
        self.next_food_id = 1
        self.next_rule_number = 1
        self.behavior_rules: dict[str, BehaviorRule] = {}
        self.next_mystery_number = 1
        self.mysteries: dict[str, MysteryObject] = {}
        self.event_sequence = 0
        self.pending_events: list[Event] = []
        self.births_total = 0
        self.deaths_total = 0
        self._food_index = SpatialFoodIndex()
        if initialize:
            self._initialize_world()

    def _initialize_world(self) -> None:
        for _ in range(self.config.initial_food):
            self._spawn_food(emit_event=False)
        for _ in range(self.config.initial_slimes):
            slime = self._new_founder()
            self.slimes[slime.id] = slime
        self._emit("world_initialized", payload={"seed": self.config.seed})

    def _new_founder(self) -> Slime:
        slime_id = self._allocate_slime_id()
        max_founder_age = max(
            1,
            int(
                self.config.base_max_age_ticks
                * self.config.founder_age_max_fraction
            ),
        )
        founder_age = self.rng.randrange(0, max_founder_age)
        return Slime(
            id=slime_id,
            parent_id=None,
            generation=0,
            x=self.rng.uniform(0.0, self.config.width),
            y=self.rng.uniform(0.0, self.config.height),
            heading=self.rng.uniform(-math.pi, math.pi),
            energy=self.config.initial_energy,
            health=100.0,
            age_ticks=founder_age,
            born_tick=-founder_age,
            last_reproduction_tick=-self.config.reproduction_cooldown_ticks,
            genome=random_genome(self.rng),
        )

    def _allocate_slime_id(self) -> str:
        slime_id = f"SLM-{self.next_slime_number:06d}"
        self.next_slime_number += 1
        return slime_id

    def _spawn_food(self, *, emit_event: bool = True) -> Food:
        return self._spawn_food_at(
            self.rng.uniform(0.0, self.config.width),
            self.rng.uniform(0.0, self.config.height),
            emit_event=emit_event,
            event_type="food_spawned",
        )

    def _spawn_food_at(
        self,
        x: float,
        y: float,
        *,
        emit_event: bool,
        event_type: str,
    ) -> Food:
        food = Food(
            id=self.next_food_id,
            x=min(self.config.width, max(0.0, x)),
            y=min(self.config.height, max(0.0, y)),
            nutrition=self.config.food_nutrition,
        )
        self.next_food_id += 1
        self.foods[food.id] = food
        self._food_index.add(food)
        if emit_event:
            self._emit(event_type, payload={"food_id": food.id, "x": food.x, "y": food.y})
        return food

    def _remove_food(self, food: Food) -> None:
        self._food_index.remove(food)
        self.foods.pop(food.id, None)

    def _emit(
        self,
        event_type: str,
        subject_id: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self.event_sequence += 1
        self.pending_events.append(
            Event(
                sequence=self.event_sequence,
                tick=self.tick,
                type=event_type,
                subject_id=subject_id,
                payload=payload or {},
            )
        )

    def add_behavior_rule(
        self, payload: dict, *, source: str = "manual"
    ) -> BehaviorRule:
        validate_rule_payload(payload, require_id=False)
        rule_id = f"RULE-{self.next_rule_number:06d}"
        self.next_rule_number += 1
        data = dict(payload)
        data["id"] = rule_id
        data["source"] = source
        data.setdefault("enabled", True)
        rule = BehaviorRule.from_dict(data)
        self.behavior_rules[rule.id] = rule
        self._emit(
            "behavior_rule_added",
            payload={"rule": rule.to_dict()},
        )
        return rule

    def remove_behavior_rule(self, rule_id: str) -> None:
        if rule_id not in self.behavior_rules:
            raise KeyError(rule_id)
        rule = self.behavior_rules.pop(rule_id)
        self._emit("behavior_rule_removed", payload={"rule": rule.to_dict()})

    def add_mystery(
        self, payload: dict, *, source: str = "manual"
    ) -> MysteryObject:
        validate_mystery_payload(payload, require_id=False)
        mystery_id = f"MYS-{self.next_mystery_number:06d}"
        self.next_mystery_number += 1
        data = dict(payload)
        data["id"] = mystery_id
        data["source"] = source
        data.setdefault("active", True)
        mystery = MysteryObject.from_dict(data)
        mystery.x = min(self.config.width, max(0.0, mystery.x))
        mystery.y = min(self.config.height, max(0.0, mystery.y))
        self.mysteries[mystery.id] = mystery
        self._emit("mystery_added", payload=mystery.public_dict())
        return mystery

    def remove_mystery(self, mystery_id: str) -> None:
        if mystery_id not in self.mysteries:
            raise KeyError(mystery_id)
        mystery = self.mysteries.pop(mystery_id)
        self._emit("mystery_removed", payload=mystery.public_dict())

    def player_deposit_food(self, x: float, y: float, count: int = 1) -> list[int]:
        if count < 1 or count > 100:
            raise ValueError("count must be in [1, 100]")
        ids: list[int] = []
        for _ in range(count):
            food = self._spawn_food_at(
                x,
                y,
                emit_event=False,
                event_type="player_food_deposit",
            )
            ids.append(food.id)
        self._emit(
            "player_food_deposit",
            payload={"x": x, "y": y, "count": count, "food_ids": ids},
        )
        return ids

    def player_emit_signal(
        self,
        signal: str,
        x: float,
        y: float,
        radius: float | None = None,
    ) -> int:
        self._validate_signal(signal)
        return self._broadcast_signal(
            signal=signal,
            x=x,
            y=y,
            radius=radius or self.config.signal_radius,
            source_id=None,
            event_type="player_signal",
        )

    def _validate_signal(self, signal: str) -> None:
        if signal not in self.SIGNALS:
            raise ValueError(f"Unknown signal {signal!r}; expected one of {self.SIGNALS}")

    def _broadcast_signal(
        self,
        *,
        signal: str,
        x: float,
        y: float,
        radius: float,
        source_id: str | None,
        event_type: str,
    ) -> int:
        self._validate_signal(signal)
        radius = max(0.1, radius)
        receivers = 0
        for slime in self.slimes.values():
            if slime.id == source_id or not slime.alive:
                continue
            if math.hypot(slime.x - x, slime.y - y) > radius:
                continue
            self._record_heard_signal(slime, signal, x, y, source_id)
            receivers += 1
        self._emit(
            event_type,
            subject_id=source_id,
            payload={
                "signal": signal,
                "x": x,
                "y": y,
                "radius": radius,
                "receivers": receivers,
            },
        )
        return receivers

    def _record_heard_signal(
        self,
        slime: Slime,
        signal: str,
        x: float,
        y: float,
        source_id: str | None,
    ) -> None:
        slime.heard_signals = [h for h in slime.heard_signals if h.signal != signal]
        slime.heard_signals.append(
            HeardSignal(signal=signal, x=x, y=y, tick=self.tick, source_id=source_id)
        )
        if source_id is not None and source_id in self.slimes:
            self._touch_relation(slime, self.slimes[source_id], scale=0.25)

    def step(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("count must be >= 0")
        for _ in range(count):
            self._step_once()

    def _step_once(self) -> None:
        self.tick += 1

        if (
            len(self.foods) < self.config.max_food
            and self.rng.random() < self.config.food_spawn_probability
        ):
            self._spawn_food()

        actor_ids = tuple(sorted(self.slimes))
        newborns: list[Slime] = []
        dead_ids: list[str] = []

        for slime_id in actor_ids:
            slime = self.slimes.get(slime_id)
            if slime is None or not slime.alive:
                continue
            child = self._advance_slime(slime)
            if child is not None:
                newborns.append(child)
            if not slime.alive:
                dead_ids.append(slime.id)

        for slime_id in dead_ids:
            self.slimes.pop(slime_id, None)
            for other in self.slimes.values():
                other.relations.pop(slime_id, None)

        for child in newborns:
            self.slimes[child.id] = child

        if self.tick % self.config.social_update_interval == 0:
            self._process_social_interactions()

    def _matching_behavior_rule(self, slime: Slime) -> BehaviorRule | None:
        for rule in sorted(
            self.behavior_rules.values(),
            key=lambda item: (-item.priority, item.id),
        ):
            if rule_matches(rule, slime):
                return rule
        return None

    def _rule_directive(
        self, slime: Slime
    ) -> tuple[BehaviorRule | None, float | None, float | None, bool]:
        rule = self._matching_behavior_rule(slime)
        if rule is None:
            return None, None, None, False

        action = rule.action
        if action == "rest":
            return rule, None, None, True
        if action == "explore":
            return rule, None, None, False
        if action == "move_to_point":
            return (
                rule,
                float(rule.parameters["x"]),
                float(rule.parameters["y"]),
                False,
            )
        if action == "seek_memory":
            memory = best_food_memory(
                slime.memories, self.tick, self.config.memory_decay
            )
            if memory is not None:
                return rule, memory.x, memory.y, False
            return None, None, None, False
        if action == "follow_signal":
            heard = self._best_signal_target(slime)
            if heard is not None:
                return rule, heard.x, heard.y, False
            return None, None, None, False
        if action == "follow_social":
            target = self._best_social_target(slime)
            if target is not None:
                return rule, target.x, target.y, False
            return None, None, None, False
        return None, None, None, False

    def _advance_slime(self, slime: Slime) -> Slime | None:
        cfg = self.config
        slime.age_ticks += 1
        self._expire_heard_signals(slime)

        perception_radius = 4.0 + 12.0 * slime.genome.perception
        hungry = slime.energy < cfg.forage_energy_threshold
        visible_food: Food | None = None
        if hungry:
            visible_food, _ = self._food_index.nearest(
                self.foods, slime.x, slime.y, perception_radius
            )

        target_x: float | None = None
        target_y: float | None = None
        remembered_target = None
        matched_rule, rule_x, rule_y, rule_rest = self._rule_directive(slime)
        rule_applied = matched_rule is not None
        if rule_applied:
            target_x, target_y = rule_x, rule_y
            slime.current_action = f"rule:{matched_rule.id}:{matched_rule.action}"

        if not rule_applied and visible_food is not None:
            target_x, target_y = visible_food.x, visible_food.y
            slime.current_action = "seek_visible_food"
            remember_food(
                slime.memories,
                x=visible_food.x,
                y=visible_food.y,
                tick=self.tick,
                strength=0.65,
                merge_radius=cfg.memory_merge_radius,
                capacity=slime.memory_capacity,
                decay=cfg.memory_decay,
            )
            self._maybe_emit_learned_signal(slime, visible_food)
        elif not rule_applied and hungry:
            signal_target = self._best_signal_target(slime)
            if signal_target is not None:
                target_x, target_y = signal_target.x, signal_target.y
                slime.current_action = f"follow_signal_{signal_target.signal}"
            else:
                remembered_target = best_food_memory(
                    slime.memories, self.tick, cfg.memory_decay
                )
                if remembered_target is not None:
                    target_x, target_y = remembered_target.x, remembered_target.y
                    slime.current_action = "seek_remembered_food"
                else:
                    slime.current_action = "explore_hungry"
        elif not rule_applied:
            social_target = self._best_social_target(slime)
            if social_target is not None:
                target_x, target_y = social_target.x, social_target.y
                slime.current_action = f"follow_{social_target.id}"
            else:
                slime.current_action = "explore_satiated"

        if target_x is not None and target_y is not None:
            desired = math.atan2(target_y - slime.y, target_x - slime.x)
            turn_noise = self.rng.gauss(0.0, 0.06 + 0.22 * slime.genome.curiosity)
            slime.heading = desired + turn_noise
        else:
            slime.heading += self.rng.gauss(
                0.0, 0.08 + 0.55 * slime.genome.curiosity
            )

        speed = 0.0 if rule_rest else 0.22 + 1.18 * slime.genome.speed
        old_x, old_y = slime.x, slime.y
        slime.x = min(
            cfg.width, max(0.0, slime.x + math.cos(slime.heading) * speed)
        )
        slime.y = min(
            cfg.height, max(0.0, slime.y + math.sin(slime.heading) * speed)
        )
        distance = math.hypot(slime.x - old_x, slime.y - old_y)
        slime.distance_travelled += distance
        self._trigger_mysteries(slime)

        metabolic_factor = 0.55 + slime.genome.metabolism
        slime.energy -= cfg.base_metabolic_cost * metabolic_factor
        slime.energy -= cfg.move_energy_cost * distance * metabolic_factor

        if slime.energy < cfg.eat_energy_threshold:
            edible, edible_distance = self._food_index.nearest(
                self.foods, slime.x, slime.y, cfg.eat_radius
            )
        else:
            edible, edible_distance = None, float("inf")

        if edible is not None and edible_distance <= cfg.eat_radius:
            slime.energy = min(cfg.max_energy, slime.energy + edible.nutrition)
            slime.food_eaten += 1
            slime.current_action = "eat"
            remember_food(
                slime.memories,
                x=edible.x,
                y=edible.y,
                tick=self.tick,
                strength=1.0,
                merge_radius=cfg.memory_merge_radius,
                capacity=slime.memory_capacity,
                decay=cfg.memory_decay,
            )
            self._learn_signal_food_associations(slime)
            self._remove_food(edible)
            self._emit("food_eaten", slime.id, {"food_id": edible.id})
        elif remembered_target is not None:
            if (
                math.hypot(
                    slime.x - remembered_target.x, slime.y - remembered_target.y
                )
                <= cfg.eat_radius
            ):
                remembered_target.strength *= 0.45

        if slime.energy < cfg.low_energy_health_threshold:
            slime.health -= cfg.low_energy_health_loss
        elif slime.energy > cfg.low_energy_health_threshold * 2:
            slime.health = min(100.0, slime.health + cfg.health_recovery)

        max_age = int(
            cfg.base_max_age_ticks
            * (0.88 + 0.24 * (1.0 - slime.genome.metabolism))
        )
        if slime.energy <= 0.0 or slime.health <= 0.0 or slime.age_ticks >= max_age:
            slime.alive = False
            self.deaths_total += 1
            cause = (
                "starvation"
                if slime.energy <= 0.0
                else "health"
                if slime.health <= 0.0
                else "age"
            )
            self._emit(
                "death", slime.id, {"cause": cause, "age_ticks": slime.age_ticks}
            )
            return None

        return self._maybe_reproduce(slime)

    def _trigger_mysteries(self, slime: Slime) -> None:
        cfg = self.config
        for mystery in sorted(self.mysteries.values(), key=lambda item: item.id):
            if not mystery.active:
                continue
            if math.hypot(slime.x - mystery.x, slime.y - mystery.y) > mystery.radius:
                continue
            last = mystery.last_trigger_by.get(slime.id, -1_000_000)
            if self.tick - last < cfg.mystery_trigger_cooldown:
                continue

            mystery.last_trigger_by[slime.id] = self.tick
            mystery.trigger_count += 1
            mystery.discoveries[slime.id] = mystery.discoveries.get(slime.id, 0) + 1

            if mystery.effect == "energy_delta":
                amount = float(mystery.parameters["amount"])
                slime.energy = min(cfg.max_energy, max(0.0, slime.energy + amount))
            elif mystery.effect == "health_delta":
                amount = float(mystery.parameters["amount"])
                slime.health = min(100.0, max(0.0, slime.health + amount))
            elif mystery.effect == "memory_amplify":
                factor = float(mystery.parameters["factor"])
                for memory in slime.memories:
                    memory.strength = min(1.0, memory.strength * factor)
            elif mystery.effect == "signal_pulse":
                signal = str(mystery.parameters["signal"])
                radius = float(mystery.parameters.get("radius", cfg.signal_radius))
                self._broadcast_signal(
                    signal=signal,
                    x=mystery.x,
                    y=mystery.y,
                    radius=radius,
                    source_id=slime.id,
                    event_type="mystery_signal",
                )

            self._emit(
                "mystery_triggered",
                subject_id=slime.id,
                payload={"mystery_id": mystery.id, "public_label": mystery.public_label},
            )
            if mystery.discoveries[slime.id] == 3:
                self._emit(
                    "mystery_discovered",
                    subject_id=slime.id,
                    payload={"mystery_id": mystery.id, "public_label": mystery.public_label},
                )

    def _expire_heard_signals(self, slime: Slime) -> None:
        cutoff = self.tick - self.config.signal_association_window
        active: list[HeardSignal] = []
        for heard in slime.heard_signals:
            if heard.tick >= cutoff:
                active.append(heard)
                continue
            old = slime.signal_food_associations.get(heard.signal, 0.0)
            if old > 0.0:
                slime.signal_food_associations[heard.signal] = max(
                    0.0, old * (1.0 - self.config.signal_extinction_rate)
                )
        slime.heard_signals = active

    def _learn_signal_food_associations(self, slime: Slime) -> None:
        cutoff = self.tick - self.config.signal_association_window
        for heard in slime.heard_signals:
            if heard.tick < cutoff:
                continue
            previous = slime.signal_food_associations.get(heard.signal, 0.0)
            updated = previous + self.config.signal_learning_rate * (1.0 - previous)
            slime.signal_food_associations[heard.signal] = min(1.0, updated)
            self._emit(
                "signal_food_learning",
                slime.id,
                {
                    "signal": heard.signal,
                    "before": previous,
                    "after": slime.signal_food_associations[heard.signal],
                    "source_id": heard.source_id,
                },
            )

    def _best_signal_target(self, slime: Slime) -> HeardSignal | None:
        candidates: list[tuple[float, int, HeardSignal]] = []
        cutoff = self.tick - self.config.signal_association_window
        for heard in slime.heard_signals:
            if heard.tick < cutoff:
                continue
            strength = slime.signal_food_associations.get(heard.signal, 0.0)
            if strength >= self.config.signal_response_threshold:
                candidates.append((strength, heard.tick, heard))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2].signal), reverse=True)
        return candidates[0][2]

    def _maybe_emit_learned_signal(self, slime: Slime, food: Food) -> None:
        cfg = self.config
        if self.tick - slime.last_signal_emit_tick < cfg.signal_emit_cooldown:
            return
        if not slime.signal_food_associations:
            return
        signal, strength = max(
            slime.signal_food_associations.items(), key=lambda item: (item[1], item[0])
        )
        if strength < cfg.signal_emit_threshold:
            return
        probability = cfg.signal_emit_probability * (0.25 + slime.genome.sociability)
        if self.rng.random() >= probability:
            return
        slime.last_signal_emit_tick = self.tick
        self._broadcast_signal(
            signal=signal,
            x=food.x,
            y=food.y,
            radius=cfg.signal_radius,
            source_id=slime.id,
            event_type="slime_signal",
        )

    def _best_social_target(self, slime: Slime) -> Slime | None:
        cfg = self.config
        candidates: list[tuple[float, str, Slime]] = []
        for target_id, relation in slime.relations.items():
            if relation.familiarity < cfg.social_follow_threshold:
                continue
            target = self.slimes.get(target_id)
            if target is None or not target.alive:
                continue
            distance = math.hypot(target.x - slime.x, target.y - slime.y)
            if distance > cfg.social_follow_radius:
                continue
            candidates.append((relation.familiarity, target.id, target))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        chance = 0.04 + 0.18 * slime.genome.sociability
        if self.rng.random() >= chance:
            return None
        return candidates[0][2]

    def _process_social_interactions(self) -> None:
        if len(self.slimes) < 2:
            return
        cfg = self.config
        index = SpatialSlimeIndex(cell_size=max(2.0, cfg.social_interaction_radius * 2.0))
        for slime in self.slimes.values():
            index.add(slime.id, slime.x, slime.y)

        handled: set[tuple[str, str]] = set()
        for slime in sorted(self.slimes.values(), key=lambda item: item.id):
            for other_id, _ in index.neighbors(
                slime.x, slime.y, cfg.social_interaction_radius
            ):
                if other_id == slime.id:
                    continue
                pair = tuple(sorted((slime.id, other_id)))
                if pair in handled:
                    continue
                handled.add(pair)
                other = self.slimes.get(other_id)
                if other is None:
                    continue
                self._touch_relation(slime, other)
                self._touch_relation(other, slime)

    def _touch_relation(self, owner: Slime, other: Slime, scale: float = 1.0) -> None:
        cfg = self.config
        relation = owner.relations.setdefault(other.id, Relation())
        learning = (
            cfg.social_learning_rate
            * scale
            * (0.35 + 0.65 * owner.genome.sociability)
        )
        relation.familiarity += learning * (1.0 - relation.familiarity)
        if owner.energy >= cfg.forage_energy_threshold and other.energy >= cfg.forage_energy_threshold:
            relation.trust += 0.15 * learning * (1.0 - relation.trust)
        relation.familiarity = min(1.0, max(0.0, relation.familiarity))
        relation.trust = min(1.0, max(-1.0, relation.trust))
        relation.interactions += 1
        relation.last_interaction_tick = self.tick

        if len(owner.relations) > cfg.max_relations_per_slime:
            worst_id, _ = min(
                owner.relations.items(),
                key=lambda item: (
                    item[1].familiarity,
                    item[1].last_interaction_tick,
                    item[0],
                ),
            )
            owner.relations.pop(worst_id, None)

    def _maybe_reproduce(self, slime: Slime) -> Slime | None:
        cfg = self.config
        if slime.age_ticks < cfg.maturity_age_ticks:
            return None
        if slime.energy < cfg.reproduction_energy_threshold:
            return None
        if self.tick - slime.last_reproduction_tick < cfg.reproduction_cooldown_ticks:
            return None

        probability = cfg.base_reproduction_probability * (0.25 + slime.genome.fertility)
        if self.rng.random() >= probability:
            return None

        child_genome = mutate_genome(
            slime.genome,
            self.rng,
            mutation_rate=cfg.mutation_rate,
            sigma=cfg.mutation_sigma,
        )
        angle = self.rng.uniform(-math.pi, math.pi)
        radius = self.rng.uniform(0.25, 1.5)
        child = Slime(
            id=self._allocate_slime_id(),
            parent_id=slime.id,
            generation=slime.generation + 1,
            x=min(cfg.width, max(0.0, slime.x + math.cos(angle) * radius)),
            y=min(cfg.height, max(0.0, slime.y + math.sin(angle) * radius)),
            heading=self.rng.uniform(-math.pi, math.pi),
            energy=min(cfg.birth_energy, cfg.reproduction_energy_cost),
            health=100.0,
            age_ticks=0,
            born_tick=self.tick,
            last_reproduction_tick=self.tick,
            genome=child_genome,
        )
        slime.energy -= cfg.reproduction_energy_cost
        slime.last_reproduction_tick = self.tick
        slime.offspring_count += 1
        self.births_total += 1
        self._emit(
            "birth",
            child.id,
            {"parent_id": slime.id, "generation": child.generation},
        )
        return child

    def metrics(self) -> WorldMetrics:
        living = list(self.slimes.values())
        if living:
            mean_energy = sum(s.energy for s in living) / len(living)
            mean_health = sum(s.health for s in living) / len(living)
            max_generation = max(s.generation for s in living)
        else:
            mean_energy = mean_health = 0.0
            max_generation = 0
        return WorldMetrics(
            tick=self.tick,
            population=len(living),
            food_count=len(self.foods),
            births=self.births_total,
            deaths=self.deaths_total,
            mean_energy=mean_energy,
            mean_health=mean_health,
            max_generation=max_generation,
        )

    def replace_foods(self, foods: Iterable[Food]) -> None:
        self.foods = {food.id: food for food in foods}
        self._food_index = SpatialFoodIndex()
        for food in self.foods.values():
            self._food_index.add(food)

    def rng_state_bytes(self) -> bytes:
        return pickle.dumps(self.rng.getstate(), protocol=pickle.HIGHEST_PROTOCOL)

    def restore_rng_state(self, state: bytes) -> None:
        self.rng.setstate(pickle.loads(state))

    def state_digest(self) -> str:
        state = {
            "tick": self.tick,
            "next_slime_number": self.next_slime_number,
            "next_food_id": self.next_food_id,
            "next_rule_number": self.next_rule_number,
            "behavior_rules": [
                rule.to_dict()
                for rule in sorted(self.behavior_rules.values(), key=lambda item: item.id)
            ],
            "next_mystery_number": self.next_mystery_number,
            "mysteries": [
                mystery.to_dict(include_hidden=True)
                for mystery in sorted(self.mysteries.values(), key=lambda item: item.id)
            ],
            "event_sequence": self.event_sequence,
            "births_total": self.births_total,
            "deaths_total": self.deaths_total,
            "slimes": [
                {
                    "id": s.id,
                    "parent_id": s.parent_id,
                    "generation": s.generation,
                    "x": s.x,
                    "y": s.y,
                    "heading": s.heading,
                    "energy": s.energy,
                    "health": s.health,
                    "age_ticks": s.age_ticks,
                    "born_tick": s.born_tick,
                    "last_reproduction_tick": s.last_reproduction_tick,
                    "genome": s.genome.to_dict(),
                    "memories": [
                        (m.x, m.y, m.strength, m.last_seen_tick) for m in s.memories
                    ],
                    "relations": [
                        (
                            target_id,
                            rel.familiarity,
                            rel.trust,
                            rel.interactions,
                            rel.last_interaction_tick,
                        )
                        for target_id, rel in sorted(s.relations.items())
                    ],
                    "signal_food_associations": sorted(
                        s.signal_food_associations.items()
                    ),
                    "heard_signals": [
                        (h.signal, h.x, h.y, h.tick, h.source_id)
                        for h in s.heard_signals
                    ],
                    "last_signal_emit_tick": s.last_signal_emit_tick,
                    "distance_travelled": s.distance_travelled,
                    "food_eaten": s.food_eaten,
                    "offspring_count": s.offspring_count,
                    "current_action": s.current_action,
                    "alive": s.alive,
                }
                for s in sorted(self.slimes.values(), key=lambda item: item.id)
            ],
            "foods": [
                (f.id, f.x, f.y, f.nutrition)
                for f in sorted(self.foods.values(), key=lambda item: item.id)
            ],
            "rng": hashlib.sha256(self.rng_state_bytes()).hexdigest(),
        }
        raw = json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
