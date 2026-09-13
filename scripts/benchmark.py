from __future__ import annotations

import argparse
import time
from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.world.engine import World


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slimes", type=int, default=100)
    parser.add_argument("--ticks", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=428719)
    args = parser.parse_args()

    cfg = replace(
        WorldConfig(),
        seed=args.seed,
        initial_slimes=args.slimes,
        initial_food=max(180, args.slimes * 2),
        max_food=max(260, args.slimes * 3),
    )
    world = World(cfg)
    start = time.perf_counter()
    world.step(args.ticks)
    elapsed = time.perf_counter() - start
    agent_ticks = args.ticks * args.slimes
    print(f"ticks={args.ticks}")
    print(f"initial_slimes={args.slimes}")
    print(f"elapsed_seconds={elapsed:.6f}")
    print(f"nominal_agent_ticks_per_second={agent_ticks / elapsed:.2f}")
    print(f"final_population={len(world.slimes)}")
    print(f"digest={world.state_digest()}")


if __name__ == "__main__":
    main()
