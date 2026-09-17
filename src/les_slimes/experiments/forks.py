from __future__ import annotations

import json
import random
import sqlite3
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from ..database.base import RelationalRepository
from ..database.scope import (
    PersistenceScope,
    PersistenceScopeError,
    get_persistence_scope,
    require_persistence_scope,
    set_persistence_scope,
)
from ..database.sqlite_repo import SQLiteRepository
from ..world.engine import World


_MANIFEST_KEY = "experiment_manifest"


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    experiment_id: str
    run_id: str
    canonical: bool
    persistence_scope: str
    source_tick: int
    source_event_sequence: int
    source_digest: str
    source_git_commit: str
    source_config: dict
    created_at_utc: str
    condition: str
    experiment_seed: int | None
    rng_reseeded: bool
    initial_digest: str
    final_digest: str
    ticks_executed: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentManifest":
        return cls(**data)


def _write_manifest(repo: SQLiteRepository, manifest: ExperimentManifest) -> None:
    require_persistence_scope(repo, PersistenceScope.NON_CANONICAL_EXPERIMENT)
    with repo._connect() as conn:
        repo._set_meta(
            conn,
            _MANIFEST_KEY,
            json.dumps(manifest.to_dict(), sort_keys=True).encode("utf-8"),
        )
        conn.commit()


def read_experiment_manifest(repo: SQLiteRepository) -> ExperimentManifest:
    require_persistence_scope(repo, PersistenceScope.NON_CANONICAL_EXPERIMENT)
    with repo._connect() as conn:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (_MANIFEST_KEY,)
        ).fetchone()
    if row is None:
        raise PersistenceScopeError("Experimental database has no experiment manifest")
    raw = row["value"]
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return ExperimentManifest.from_dict(json.loads(str(raw)))


def _readonly_sqlite_backup(source: Path, destination: Path) -> None:
    source_uri = f"file:{source.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _snapshot_canonical_world(source_repository: RelationalRepository) -> World:
    """Read one coherent canonical world snapshot without copying governance.

    SQLite uses its native backup API. Other relational backends take the canonical
    write lock while reading the world through a separate read transaction. This
    prevents a world save from interleaving with the snapshot while leaving the
    resulting experiment isolated in a new SQLite database.
    """

    require_persistence_scope(source_repository, PersistenceScope.CANONICAL)
    if isinstance(source_repository, SQLiteRepository) and source_repository.backend_name == "sqlite":
        with tempfile.TemporaryDirectory(prefix="les-slimes-snapshot-") as tmpdir:
            snapshot_path = Path(tmpdir) / "canonical_snapshot.sqlite"
            _readonly_sqlite_backup(source_repository.path, snapshot_path)
            snapshot_repo = SQLiteRepository(snapshot_path)
            require_persistence_scope(snapshot_repo, PersistenceScope.CANONICAL)
            return snapshot_repo.load_world()

    with source_repository._connect() as guard_conn:
        source_repository.begin_write(guard_conn)
        try:
            return source_repository.load_world()
        finally:
            guard_conn.rollback()


def create_experiment_fork(
    source_repository: RelationalRepository,
    destination: str | Path,
    *,
    experiment_id: str,
    condition: str,
    source_git_commit: str,
    experiment_seed: int | None = None,
    run_id: str | None = None,
) -> tuple[SQLiteRepository, ExperimentManifest]:
    if not experiment_id.strip() or not condition.strip() or not source_git_commit.strip():
        raise ValueError("experiment_id, condition and source_git_commit are required")

    require_persistence_scope(source_repository, PersistenceScope.CANONICAL)
    destination_path = Path(destination)
    if (
        isinstance(source_repository, SQLiteRepository)
        and source_repository.backend_name == "sqlite"
        and destination_path.resolve() == source_repository.path.resolve()
    ):
        raise ValueError("Experiment destination must differ from canonical database")
    if destination_path.exists():
        raise FileExistsError(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    source_world = _snapshot_canonical_world(source_repository)
    source_tick = source_world.tick
    source_event_sequence = source_world.event_sequence
    source_digest = source_world.state_digest()
    source_config = source_world.config.to_dict()

    experiment_repo = SQLiteRepository(destination_path)
    set_persistence_scope(experiment_repo, PersistenceScope.NON_CANONICAL_EXPERIMENT)
    experiment_world = source_world
    if experiment_seed is not None:
        experiment_world.rng = random.Random(int(experiment_seed))
    experiment_repo.save_world(experiment_world)
    initial_digest = experiment_world.state_digest()

    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        run_id=run_id or f"RUN-{uuid.uuid4().hex}",
        canonical=False,
        persistence_scope=PersistenceScope.NON_CANONICAL_EXPERIMENT.value,
        source_tick=source_tick,
        source_event_sequence=source_event_sequence,
        source_digest=source_digest,
        source_git_commit=source_git_commit,
        source_config=source_config,
        created_at_utc=datetime.now(UTC).isoformat(),
        condition=condition,
        experiment_seed=experiment_seed,
        rng_reseeded=experiment_seed is not None,
        initial_digest=initial_digest,
        final_digest=initial_digest,
        ticks_executed=0,
    )
    _write_manifest(experiment_repo, manifest)
    return experiment_repo, manifest


def run_experiment_fork(
    repository: SQLiteRepository,
    *,
    ticks: int,
) -> ExperimentManifest:
    if ticks < 0:
        raise ValueError("ticks must be >= 0")
    require_persistence_scope(repository, PersistenceScope.NON_CANONICAL_EXPERIMENT)
    manifest = read_experiment_manifest(repository)
    world = repository.load_world()
    world.step(ticks)
    repository.save_world(world)
    updated = replace(
        manifest,
        final_digest=world.state_digest(),
        ticks_executed=manifest.ticks_executed + ticks,
    )
    _write_manifest(repository, updated)
    return updated


def is_canonical_repository(repository: RelationalRepository) -> bool:
    return get_persistence_scope(repository) == PersistenceScope.CANONICAL
