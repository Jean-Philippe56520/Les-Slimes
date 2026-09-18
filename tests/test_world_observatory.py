from datetime import UTC, datetime, timedelta
import json

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.observer.world_observatory import (
    FilesystemObservationSink,
    ObservationSchedule,
    WorldObservationBuilder,
    WorldObservationPublisher,
)
from les_slimes.runtime import CanonicalRuntime
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=1234,
                width=30.0,
                height=20.0,
                initial_slimes=6,
                initial_food=8,
                max_food=20,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    CanonicalRuntime(repo).ensure_initialized(datetime(2026, 9, 18, 8, 0, tzinfo=UTC))
    return repo


def test_observation_builder_is_read_only_and_contains_scientific_summary(tmp_path):
    repo = build_repo(tmp_path)
    before = repo.load_world().state_digest()
    payload = WorldObservationBuilder(repo).build(
        observed_at_utc=datetime(2026, 9, 18, 8, 5, tzinfo=UTC)
    )

    assert payload["schema_version"] == 1
    assert payload["tick"] == 0
    assert payload["state_digest"] == before
    assert payload["world"]["population"] == 6
    assert payload["world"]["food_count"] == 8
    assert set(payload["genetics"]["traits"]) == {
        "speed",
        "metabolism",
        "perception",
        "fertility",
        "curiosity",
        "sociability",
    }
    assert payload["runtime"]["ticks_due"] == 300
    assert repo.load_world().state_digest() == before


def test_publisher_writes_latest_snapshot_and_daily_atomically(tmp_path):
    repo = build_repo(tmp_path)
    output = tmp_path / "observations"
    publisher = WorldObservationPublisher(
        repo,
        FilesystemObservationSink(output),
        schedule=ObservationSchedule(
            latest_interval_seconds=30,
            snapshot_interval_seconds=60,
            daily_interval_seconds=120,
        ),
    )
    start = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)

    assert publisher.maybe_publish(observed_at_utc=start) == (
        "latest",
        "snapshot",
        "daily",
    )
    assert publisher.maybe_publish(observed_at_utc=start + timedelta(seconds=10)) == ()
    assert publisher.maybe_publish(observed_at_utc=start + timedelta(seconds=31)) == ("latest",)

    latest = json.loads((output / "LATEST_WORLD_STATE.json").read_text(encoding="utf-8"))
    assert latest["tick"] == 0
    assert list((output / "snapshots").glob("snapshot-*.json"))
    assert list((output / "daily").glob("daily-*.json"))
