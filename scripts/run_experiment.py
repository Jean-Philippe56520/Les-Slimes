from __future__ import annotations

import argparse
from pathlib import Path

from les_slimes.config import WorldConfig
from les_slimes.experiments import export_batch, run_batch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--ticks", type=int, default=10000)
    parser.add_argument("--seeds", nargs="+", type=int, default=[428719, 9137, 20260913])
    parser.add_argument("--output-dir", default="experiments/results")
    parser.add_argument("--name", default="baseline")
    args = parser.parse_args()

    config = WorldConfig.from_yaml(args.config)
    results = run_batch(config, seeds=args.seeds, ticks=args.ticks)
    csv_path, json_path = export_batch(results, Path(args.output_dir), args.name)
    print(csv_path)
    print(json_path)


if __name__ == "__main__":
    main()
