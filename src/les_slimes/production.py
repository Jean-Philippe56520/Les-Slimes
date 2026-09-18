from __future__ import annotations

import argparse
import json
import os
import signal
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .api.app import create_app
from .config import WorldConfig
from .database.factory import DATABASE_URL_ENV, canonical_repository_from_env
from .database.migrate import migrate_sqlite_to_postgres
from .database.postgres_repo import PostgreSQLRepository
from .database.sqlite_repo import SQLiteRepository
from .observer.world_observatory import FilesystemObservationSink, ObservationSchedule, WorldObservationPublisher
from .runtime import CanonicalRuntime, CanonicalWorkerService, RuntimeStorage, WorkerServiceConfig
from .world.engine import World


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def create_api_app():
    """Uvicorn factory using the configured canonical persistence backend."""
    return create_app(canonical_repository_from_env())


def _service() -> CanonicalWorkerService:
    repository = canonical_repository_from_env()
    observation_dir = os.getenv("LES_SLIMES_OBSERVATION_DIR", "").strip()
    publisher = None
    if observation_dir:
        publisher = WorldObservationPublisher(
            repository,
            FilesystemObservationSink(observation_dir),
            schedule=ObservationSchedule(
                latest_interval_seconds=_float_env("LES_SLIMES_OBSERVATION_LATEST_SECONDS", 1800.0),
                snapshot_interval_seconds=_float_env("LES_SLIMES_OBSERVATION_SNAPSHOT_SECONDS", 21600.0),
                daily_interval_seconds=_float_env("LES_SLIMES_OBSERVATION_DAILY_SECONDS", 86400.0),
            ),
        )
    return CanonicalWorkerService(
        repository,
        holder_id=os.getenv("LES_SLIMES_WORKER_ID") or None,
        config=WorkerServiceConfig(
            poll_interval_seconds=_float_env("LES_SLIMES_WORKER_POLL_SECONDS", 1.0),
            lease_ttl_seconds=_float_env("LES_SLIMES_WORKER_LEASE_TTL_SECONDS", 30.0),
            heartbeat_interval_seconds=_float_env(
                "LES_SLIMES_WORKER_HEARTBEAT_SECONDS", 10.0
            ),
            batch_size=_int_env("LES_SLIMES_WORKER_BATCH_SIZE", 1000),
            command_page_size=_int_env("LES_SLIMES_WORKER_COMMAND_PAGE_SIZE", 1000),
        ),
        observation_publisher=publisher,
    )


def _health_dict(service: CanonicalWorkerService) -> dict:
    health = service.health()
    return {
        "holder_id": health.holder_id,
        "lease_generation": health.lease_generation,
        "lease_expires_at_utc": (
            health.lease_expires_at_utc.isoformat()
            if health.lease_expires_at_utc is not None
            else None
        ),
        "lease_valid": health.lease_valid,
        "world_tick": health.world_tick,
        "last_simulated_at_utc": health.last_simulated_at_utc.isoformat(),
        "wall_clock_utc": health.wall_clock_utc.isoformat(),
        "lag_seconds": health.lag_seconds,
        "ticks_due": health.ticks_due,
        "pending_commands": health.pending_commands,
        "oldest_pending_command_utc": (
            health.oldest_pending_command_utc.isoformat()
            if health.oldest_pending_command_utc is not None
            else None
        ),
    }


def cmd_init(args: argparse.Namespace) -> int:
    repo = canonical_repository_from_env()
    if repo.exists():
        raise RuntimeError("Canonical database already contains a world; refusing to overwrite it")
    config = WorldConfig.from_yaml(args.config)
    world = World(config)
    repo.save_world(world)
    RuntimeStorage(repo)
    CanonicalRuntime(repo).ensure_initialized(datetime.now(UTC))
    print(
        json.dumps(
            {
                "backend": repo.backend_name,
                "tick": world.tick,
                "population": world.metrics().population,
                "state_digest": world.state_digest(),
            },
            indent=2,
        )
    )
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    target = canonical_repository_from_env()
    if not isinstance(target, PostgreSQLRepository):
        raise RuntimeError(
            f"{DATABASE_URL_ENV} must select PostgreSQL for the migration target"
        )
    source = SQLiteRepository(args.sqlite)
    result = migrate_sqlite_to_postgres(source, target)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


def cmd_worker(_args: argparse.Namespace) -> int:
    service = _service()
    stop = threading.Event()

    def request_stop(signum, frame) -> None:
        del signum, frame
        stop.set()

    previous_sigint = signal.signal(signal.SIGINT, request_stop)
    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    try:
        service.serve(stop_requested=stop.is_set)
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    service = _service()
    print(json.dumps(_health_dict(service), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="les-slimes-production")
    parser.description = (
        f"Production entrypoint. PostgreSQL is selected with {DATABASE_URL_ENV}; "
        "otherwise SQLite is used."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize an empty canonical database once")
    init.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[2] / "config" / "default.yaml"),
    )
    init.set_defaults(func=cmd_init)

    migrate = sub.add_parser(
        "migrate",
        help="Migrate a stopped canonical SQLite world into a fresh PostgreSQL database",
    )
    migrate.add_argument("--sqlite", required=True, help="Path to the canonical SQLite DB")
    migrate.set_defaults(func=cmd_migrate)

    worker = sub.add_parser("worker", help="Run the canonical worker continuously")
    worker.set_defaults(func=cmd_worker)

    status = sub.add_parser("status", help="Read worker/canonical health")
    status.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
