from __future__ import annotations

import csv
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Iterable

from ..analytics import build_world_report
from ..config import WorldConfig
from ..world.engine import World
from ..world.modes import WorldMode


def run_batch(
    base_config: WorldConfig,
    *,
    seeds: Iterable[int],
    ticks: int,
) -> list[dict]:
    if ticks < 0:
        raise ValueError("ticks must be >= 0")
    results: list[dict] = []
    for seed in seeds:
        cfg = replace(base_config, seed=int(seed))
        world = World(cfg, mode=WorldMode.EXPERIMENT)
        world.step(ticks)
        report = build_world_report(world)
        metrics = asdict(world.metrics())
        results.append(
            {
                "seed": seed,
                "ticks": ticks,
                "digest": world.state_digest(),
                **metrics,
                "largest_social_cluster": report["social"]["largest_cluster_size"],
                "emergence_candidate_count": len(report["emergence_candidates"]),
                "report": report,
            }
        )
    return results


def export_batch(results: list[dict], output_dir: str | Path, name: str) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{name}.json"
    csv_path = output_dir / f"{name}.csv"

    json_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    scalar_rows = [
        {key: value for key, value in row.items() if key != "report"}
        for row in results
    ]
    fieldnames = list(scalar_rows[0].keys()) if scalar_rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(scalar_rows)
    return csv_path, json_path
