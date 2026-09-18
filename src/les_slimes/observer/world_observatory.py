from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import fmean, pstdev
from typing import Protocol

from ..database.base import RelationalRepository
from ..runtime.canonical import CanonicalRuntime


@dataclass(frozen=True, slots=True)
class ObservationSchedule:
    latest_interval_seconds: float = 1800.0
    snapshot_interval_seconds: float = 21600.0
    daily_interval_seconds: float = 86400.0

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if value <= 0:
                raise ValueError(f"{name} must be > 0")


@dataclass(frozen=True, slots=True)
class PublishedObservation:
    kind: str
    observed_at_utc: datetime
    tick: int
    state_digest: str
    payload: dict


class ObservationSink(Protocol):
    def publish(self, observation: PublishedObservation) -> None: ...


class FilesystemObservationSink:
    """Durable export sink suitable for a mounted volume or external sync agent."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def publish(self, observation: PublishedObservation) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(observation.payload, ensure_ascii=False, sort_keys=True, indent=2)
        latest = self.root / "LATEST_WORLD_STATE.json"
        tmp = latest.with_suffix(".json.tmp")
        tmp.write_text(serialized + "\n", encoding="utf-8")
        tmp.replace(latest)

        stamp = observation.observed_at_utc.strftime("%Y%m%dT%H%M%SZ")
        if observation.kind in {"snapshot", "daily"}:
            folder = self.root / ("snapshots" if observation.kind == "snapshot" else "daily")
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{observation.kind}-{stamp}-tick-{observation.tick}.json"
            target.write_text(serialized + "\n", encoding="utf-8")


def _mean_std(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "stddev": 0.0}
    return {
        "mean": round(fmean(values), 6),
        "stddev": round(pstdev(values), 6) if len(values) > 1 else 0.0,
    }


class WorldObservationBuilder:
    def __init__(self, repository: RelationalRepository) -> None:
        self.repository = repository
        self.runtime = CanonicalRuntime(repository)

    def build(self, *, observed_at_utc: datetime) -> dict:
        now = observed_at_utc.astimezone(UTC)
        world = self.repository.load_world()
        metadata = self.runtime.inspect_metadata()
        living = [slime for slime in world.slimes.values() if slime.alive]

        action_counts = Counter(slime.current_action for slime in living)
        generation_counts = Counter(slime.generation for slime in living)
        trait_names = ("speed", "metabolism", "perception", "fertility", "curiosity", "sociability")
        genetics = {
            name: _mean_std([float(getattr(slime.genome, name)) for slime in living])
            for name in trait_names
        }
        total_relations = sum(len(slime.relations) for slime in living)
        total_memories = sum(len(slime.memories) for slime in living)
        heard_signals = sum(len(slime.heard_signals) for slime in living)
        signal_associations = sum(len(slime.signal_food_associations) for slime in living)

        metrics = asdict(world.metrics())
        lag_seconds = max(0.0, (now - metadata.last_simulated_at_utc).total_seconds())
        ticks_due = max(0, math.floor(lag_seconds / metadata.tick_duration_seconds))
        return {
            "schema_version": 1,
            "observed_at_utc": now.isoformat(),
            "tick": world.tick,
            "state_digest": world.state_digest(),
            "runtime": {
                "last_simulated_at_utc": metadata.last_simulated_at_utc.isoformat(),
                "tick_duration_seconds": metadata.tick_duration_seconds,
                "lag_seconds": round(lag_seconds, 6),
                "ticks_due": ticks_due,
            },
            "world": {
                **metrics,
                "width": world.config.width,
                "height": world.config.height,
            },
            "behaviour": {
                "action_counts": dict(sorted(action_counts.items())),
                "mean_memories_per_slime": round(total_memories / len(living), 6) if living else 0.0,
                "mean_relations_per_slime": round(total_relations / len(living), 6) if living else 0.0,
                "heard_signals_total": heard_signals,
                "signal_associations_total": signal_associations,
            },
            "genetics": {
                "traits": genetics,
                "generation_counts": {str(key): value for key, value in sorted(generation_counts.items())},
            },
        }


class WorldObservationPublisher:
    def __init__(
        self,
        repository: RelationalRepository,
        sink: ObservationSink,
        *,
        schedule: ObservationSchedule | None = None,
    ) -> None:
        self.builder = WorldObservationBuilder(repository)
        self.sink = sink
        self.schedule = schedule or ObservationSchedule()
        self.schedule.validate()
        self._last_latest: datetime | None = None
        self._last_snapshot: datetime | None = None
        self._last_daily: datetime | None = None

    @staticmethod
    def _due(last: datetime | None, now: datetime, seconds: float) -> bool:
        return last is None or now - last >= timedelta(seconds=seconds)

    def maybe_publish(self, *, observed_at_utc: datetime) -> tuple[str, ...]:
        now = observed_at_utc.astimezone(UTC)
        due_latest = self._due(self._last_latest, now, self.schedule.latest_interval_seconds)
        due_snapshot = self._due(self._last_snapshot, now, self.schedule.snapshot_interval_seconds)
        due_daily = self._due(self._last_daily, now, self.schedule.daily_interval_seconds)
        if not (due_latest or due_snapshot or due_daily):
            return ()

        payload = self.builder.build(observed_at_utc=now)
        emitted: list[str] = []
        if due_latest:
            self.sink.publish(PublishedObservation("latest", now, payload["tick"], payload["state_digest"], payload))
            self._last_latest = now
            emitted.append("latest")
        if due_snapshot:
            self.sink.publish(PublishedObservation("snapshot", now, payload["tick"], payload["state_digest"], payload))
            self._last_snapshot = now
            emitted.append("snapshot")
        if due_daily:
            self.sink.publish(PublishedObservation("daily", now, payload["tick"], payload["state_digest"], payload))
            self._last_daily = now
            emitted.append("daily")
        return tuple(emitted)
