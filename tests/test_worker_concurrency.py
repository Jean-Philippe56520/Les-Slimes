from datetime import UTC, datetime
from threading import Barrier, Lock, Thread

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import RuntimeStorage
from les_slimes.world.engine import World


def test_simultaneous_lease_acquisition_has_single_winner(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=3030,
                initial_slimes=4,
                initial_food=6,
                max_food=20,
                food_spawn_probability=0.0,
            )
        )
    )
    storage = RuntimeStorage(repo)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    barrier = Barrier(3)
    lock = Lock()
    results = []

    def contender(holder_id: str) -> None:
        barrier.wait()
        lease = storage.acquire_lease(
            holder_id=holder_id,
            now_utc=now,
            ttl_seconds=30,
        )
        with lock:
            results.append(lease)

    threads = [
        Thread(target=contender, args=("worker-a",)),
        Thread(target=contender, args=("worker-b",)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    winners = [lease for lease in results if lease is not None]
    assert len(winners) == 1
    assert winners[0].holder_id in {"worker-a", "worker-b"}
