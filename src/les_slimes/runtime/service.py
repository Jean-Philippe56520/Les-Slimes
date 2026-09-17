from __future__ import annotations

import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol

from ..database.base import RelationalRepository
from .canonical import CanonicalRuntime
from .storage import WriterLease
from .worker import CanonicalWorldWorker, WorkerRunResult


class ServiceClock(Protocol):
    def now(self) -> datetime: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass(frozen=True, slots=True)
class WorkerServiceConfig:
    poll_interval_seconds: float = 1.0
    lease_ttl_seconds: float = 30.0
    heartbeat_interval_seconds: float = 10.0
    batch_size: int = 1000
    command_page_size: int = 1000

    def validate(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        if self.lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be > 0")
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be > 0")
        if self.heartbeat_interval_seconds >= self.lease_ttl_seconds:
            raise ValueError("heartbeat_interval_seconds must be < lease_ttl_seconds")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.command_page_size < 1:
            raise ValueError("command_page_size must be >= 1")


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    holder_id: str
    lease_generation: int | None
    lease_expires_at_utc: datetime | None
    lease_valid: bool
    world_tick: int
    last_simulated_at_utc: datetime
    wall_clock_utc: datetime
    lag_seconds: float
    ticks_due: int
    pending_commands: int
    oldest_pending_command_utc: datetime | None


class CanonicalWorkerService:
    def __init__(
        self,
        repository: RelationalRepository,
        *,
        config: WorkerServiceConfig | None = None,
        holder_id: str | None = None,
        clock: ServiceClock | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or WorkerServiceConfig()
        self.config.validate()
        self.clock = clock or SystemClock()
        self.holder_id = holder_id or self.default_holder_id()
        self.worker = CanonicalWorldWorker(
            repository,
            holder_id=self.holder_id,
            batch_size=self.config.batch_size,
            lease_ttl_seconds=self.config.lease_ttl_seconds,
            clock=self.clock.now,
            command_page_size=self.config.command_page_size,
        )
        self.runtime = CanonicalRuntime(repository, batch_size=self.config.batch_size)
        self.lease: WriterLease | None = None
        self.last_result: WorkerRunResult | None = None

    @staticmethod
    def default_holder_id() -> str:
        hostname = socket.gethostname() or "unknown-host"
        return f"world-worker:{hostname}:{os.getpid()}:{uuid.uuid4().hex}"

    def start(self) -> WriterLease:
        if self.lease is None:
            self.lease = self.worker.acquire_lease()
        return self.lease

    def cycle(self) -> WorkerRunResult:
        lease = self.start()
        result, refreshed = self.worker.run_until_with_lease(self.clock.now(), lease)
        self.lease = refreshed
        self.last_result = result
        return result

    def heartbeat(self) -> WriterLease:
        lease = self.start()
        self.lease = self.worker.heartbeat_lease(lease)
        return self.lease

    def close(self) -> None:
        if self.lease is not None:
            self.worker.release_lease(self.lease)
            self.lease = None

    def health(self) -> WorkerHealth:
        now = self.clock.now().astimezone(UTC)
        metadata = self.runtime.inspect_metadata()
        world = self.repository.load_world()
        lag_seconds = max(
            0.0,
            (now - metadata.last_simulated_at_utc).total_seconds(),
        )
        ticks_due = max(0, int(lag_seconds // metadata.tick_duration_seconds))
        lease = self.worker.storage.current_lease()
        lease_valid = bool(lease is not None and lease.expires_at_utc > now)
        return WorkerHealth(
            holder_id=lease.holder_id if lease_valid and lease is not None else self.holder_id,
            lease_generation=lease.generation if lease else None,
            lease_expires_at_utc=lease.expires_at_utc if lease else None,
            lease_valid=lease_valid,
            world_tick=world.tick,
            last_simulated_at_utc=metadata.last_simulated_at_utc,
            wall_clock_utc=now,
            lag_seconds=lag_seconds,
            ticks_due=ticks_due,
            pending_commands=self.worker.storage.pending_command_count(),
            oldest_pending_command_utc=self.worker.storage.oldest_pending_command_utc(),
        )

    def _idle_with_heartbeats(self, *, stop_requested: Callable[[], bool]) -> None:
        remaining = self.config.poll_interval_seconds
        while remaining > 0 and not stop_requested():
            sleep_for = min(remaining, self.config.heartbeat_interval_seconds)
            self.clock.sleep(sleep_for)
            remaining -= sleep_for
            if not stop_requested():
                self.heartbeat()

    def serve(self, *, stop_requested: Callable[[], bool]) -> None:
        self.start()
        try:
            while not stop_requested():
                self.cycle()
                if stop_requested():
                    break
                self._idle_with_heartbeats(stop_requested=stop_requested)
        finally:
            self.close()
