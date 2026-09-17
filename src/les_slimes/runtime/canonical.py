from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..database.sqlite_repo import SQLiteRepository
from ..world.engine import World


_STARTED = "runtime_world_started_at_utc"
_LAST = "runtime_last_simulated_at_utc"
_DURATION = "runtime_tick_duration_seconds"


@dataclass(frozen=True, slots=True)
class RuntimeMetadata:
    world_started_at_utc: datetime
    last_simulated_at_utc: datetime
    tick_duration_seconds: float


@dataclass(frozen=True, slots=True)
class AdvanceResult:
    previous_tick: int
    current_tick: int
    ticks_advanced: int
    batches: int
    last_simulated_at_utc: datetime
    state_digest: str


class CanonicalRuntime:
    def __init__(self, repository: SQLiteRepository, *, batch_size: int = 1000) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.repository = repository
        self.batch_size = batch_size

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Canonical timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _text(value: object) -> str:
        if isinstance(value, memoryview):
            value = value.tobytes()
        return value.decode("ascii") if isinstance(value, bytes) else str(value)

    @classmethod
    def _dt(cls, value: object) -> datetime:
        return cls._utc(datetime.fromisoformat(cls._text(value)))

    @staticmethod
    def _delta(world: World) -> timedelta:
        return timedelta(seconds=world.config.tick_duration_seconds)

    def _read(self) -> RuntimeMetadata | None:
        self.repository.initialize_schema()
        with self.repository._connect() as conn:
            rows = {
                row["key"]: row["value"]
                for row in conn.execute(
                    "SELECT key, value FROM metadata WHERE key IN (?, ?, ?)",
                    (_STARTED, _LAST, _DURATION),
                )
            }
        if not rows:
            return None
        if len(rows) != 3:
            raise RuntimeError("Canonical runtime metadata is incomplete")
        return RuntimeMetadata(
            self._dt(rows[_STARTED]),
            self._dt(rows[_LAST]),
            float(self._text(rows[_DURATION])),
        )

    def _write(self, metadata: RuntimeMetadata) -> None:
        self.repository.initialize_schema()
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.repository._set_meta(
                conn, _STARTED, metadata.world_started_at_utc.isoformat().encode("ascii")
            )
            self.repository._set_meta(
                conn, _LAST, metadata.last_simulated_at_utc.isoformat().encode("ascii")
            )
            self.repository._set_meta(
                conn, _DURATION, str(metadata.tick_duration_seconds).encode("ascii")
            )
            conn.commit()

    def _for_world(self, world: World, started: datetime) -> RuntimeMetadata:
        return RuntimeMetadata(
            started,
            started + self._delta(world) * world.tick,
            world.config.tick_duration_seconds,
        )

    def ensure_initialized(self, now: datetime) -> RuntimeMetadata:
        now = self._utc(now)
        world = self.repository.load_world()
        persisted = self._read()
        if persisted is None:
            started = now - self._delta(world) * world.tick
            persisted = self._for_world(world, started)
            self._write(persisted)
            return persisted
        if persisted.tick_duration_seconds != world.config.tick_duration_seconds:
            raise RuntimeError("Canonical tick duration differs from world configuration")
        reconciled = self._for_world(world, persisted.world_started_at_utc)
        if reconciled != persisted:
            self._write(reconciled)
        return reconciled

    def metadata(self) -> RuntimeMetadata:
        persisted = self._read()
        if persisted is None:
            raise RuntimeError("Canonical runtime is not initialized")
        world = self.repository.load_world()
        if persisted.tick_duration_seconds != world.config.tick_duration_seconds:
            raise RuntimeError("Canonical tick duration differs from world configuration")
        reconciled = self._for_world(world, persisted.world_started_at_utc)
        if reconciled != persisted:
            self._write(reconciled)
        return reconciled

    def advance_to(self, target_time: datetime) -> AdvanceResult:
        target = self._utc(target_time)
        metadata = self.ensure_initialized(target)
        world = self.repository.load_world()
        previous_tick = world.tick
        due = max(0, int((target - metadata.last_simulated_at_utc) // self._delta(world)))
        batches = 0
        remaining = due
        while remaining:
            count = min(self.batch_size, remaining)
            world.step(count)
            self.repository.save_world(world)
            metadata = self._for_world(world, metadata.world_started_at_utc)
            self._write(metadata)
            remaining -= count
            batches += 1
        return AdvanceResult(
            previous_tick,
            world.tick,
            world.tick - previous_tick,
            batches,
            metadata.last_simulated_at_utc,
            world.state_digest(),
        )
