from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.experiments import run_batch


def test_experiment_batch_is_reproducible():
    cfg = replace(
        WorldConfig(),
        initial_slimes=6,
        initial_food=10,
        max_food=20,
        base_reproduction_probability=0.0,
    )
    a = run_batch(cfg, seeds=[11, 12], ticks=80)
    b = run_batch(cfg, seeds=[11, 12], ticks=80)
    assert [row["digest"] for row in a] == [row["digest"] for row in b]
