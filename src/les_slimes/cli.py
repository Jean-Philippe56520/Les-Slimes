from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analytics import build_world_report
from .config import WorldConfig
from .database.sqlite_repo import SQLiteRepository
from .observer import ObserverProposal, apply_proposal
from .world.engine import World


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def _metrics_dict(world: World) -> dict[str, int | float | str]:
    m = world.metrics()
    return {
        "tick": m.tick,
        "population": m.population,
        "food_count": m.food_count,
        "births": m.births,
        "deaths": m.deaths,
        "mean_energy": round(m.mean_energy, 4),
        "mean_health": round(m.mean_health, 4),
        "max_generation": m.max_generation,
        "digest": world.state_digest(),
    }


def cmd_init(args: argparse.Namespace) -> int:
    db = Path(args.db)
    if db.exists() and not args.force:
        print(f"Refusing to overwrite existing database: {db}", file=sys.stderr)
        return 2
    if db.exists() and args.force:
        db.unlink()
        Path(f"{db}-wal").unlink(missing_ok=True)
        Path(f"{db}-shm").unlink(missing_ok=True)

    config = WorldConfig.from_yaml(args.config)
    world = World(config)
    repo = SQLiteRepository(db)
    repo.save_world(world)
    print(json.dumps(_metrics_dict(world), indent=2))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    world = repo.load_world()
    remaining = args.ticks
    checkpoint = args.checkpoint or world.config.checkpoint_interval
    while remaining > 0:
        batch = min(checkpoint, remaining)
        world.step(batch)
        repo.save_world(world)
        remaining -= batch
    print(json.dumps(_metrics_dict(world), indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    world = SQLiteRepository(args.db).load_world()
    print(json.dumps(_metrics_dict(world), indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    world = SQLiteRepository(args.db).load_world()
    raw = json.dumps(build_world_report(world), indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(raw + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(raw)
    return 0


def cmd_deposit_food(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    world = repo.load_world()
    ids = world.player_deposit_food(args.x, args.y, args.count)
    repo.save_world(world)
    print(json.dumps({"food_ids": ids, **_metrics_dict(world)}, indent=2))
    return 0


def cmd_signal(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    world = repo.load_world()
    receivers = world.player_emit_signal(
        args.signal, args.x, args.y, radius=args.radius
    )
    repo.save_world(world)
    print(
        json.dumps(
            {"signal": args.signal, "receivers": receivers, **_metrics_dict(world)},
            indent=2,
        )
    )
    return 0


def cmd_proposal_import(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    world = repo.load_world()
    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    proposal = ObserverProposal.from_dict(raw)
    proposal_id = repo.add_observer_proposal(world.tick, proposal.to_dict())
    print(json.dumps({"proposal_id": proposal_id, "status": "pending"}, indent=2))
    return 0


def cmd_proposal_list(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    rows = repo.list_observer_proposals(status=args.status, limit=args.limit)
    result = []
    for row in rows:
        item = dict(row)
        item["proposal"] = json.loads(item.pop("proposal_json"))
        if item.get("result_json"):
            item["result"] = json.loads(item.pop("result_json"))
        else:
            item.pop("result_json", None)
        result.append(item)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_proposal_apply(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    world = repo.load_world()
    row = repo.get_observer_proposal(args.id)
    proposal = ObserverProposal.from_dict(json.loads(row["proposal_json"]))
    result = apply_proposal(world, proposal)
    if result.get("applied"):
        repo.save_world(world)
        repo.update_observer_proposal(args.id, status="applied", result=result)
    else:
        repo.update_observer_proposal(args.id, status="reviewed", result=result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="les-slimes")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a deterministic world")
    p_init.add_argument("--db", default="data/world.sqlite")
    p_init.add_argument("--config", default=str(_default_config_path()))
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_sim = sub.add_parser("simulate", help="Advance a saved world")
    p_sim.add_argument("--db", default="data/world.sqlite")
    p_sim.add_argument("--ticks", type=int, required=True)
    p_sim.add_argument("--checkpoint", type=int, default=0)
    p_sim.set_defaults(func=cmd_simulate)

    p_status = sub.add_parser("status", help="Show current world state")
    p_status.add_argument("--db", default="data/world.sqlite")
    p_status.set_defaults(func=cmd_status)

    p_report = sub.add_parser("report", help="Build a structured emergence report")
    p_report.add_argument("--db", default="data/world.sqlite")
    p_report.add_argument("--output")
    p_report.set_defaults(func=cmd_report)

    p_food = sub.add_parser("deposit-food", help="Deposit food as the human player")
    p_food.add_argument("--db", default="data/world.sqlite")
    p_food.add_argument("--x", type=float, required=True)
    p_food.add_argument("--y", type=float, required=True)
    p_food.add_argument("--count", type=int, default=1)
    p_food.set_defaults(func=cmd_deposit_food)

    p_signal = sub.add_parser("signal", help="Emit a learnable player signal")
    p_signal.add_argument("--db", default="data/world.sqlite")
    p_signal.add_argument("--signal", choices=World.SIGNALS, required=True)
    p_signal.add_argument("--x", type=float, required=True)
    p_signal.add_argument("--y", type=float, required=True)
    p_signal.add_argument("--radius", type=float)
    p_signal.set_defaults(func=cmd_signal)

    p_prop_import = sub.add_parser(
        "proposal-import", help="Import a validated Observer proposal JSON"
    )
    p_prop_import.add_argument("--db", default="data/world.sqlite")
    p_prop_import.add_argument("--file", required=True)
    p_prop_import.set_defaults(func=cmd_proposal_import)

    p_prop_list = sub.add_parser("proposal-list", help="List Observer proposals")
    p_prop_list.add_argument("--db", default="data/world.sqlite")
    p_prop_list.add_argument("--status")
    p_prop_list.add_argument("--limit", type=int, default=100)
    p_prop_list.set_defaults(func=cmd_proposal_list)

    p_prop_apply = sub.add_parser(
        "proposal-apply", help="Apply a safe Observer proposal"
    )
    p_prop_apply.add_argument("--db", default="data/world.sqlite")
    p_prop_apply.add_argument("--id", type=int, required=True)
    p_prop_apply.set_defaults(func=cmd_proposal_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "ticks", 0) < 0:
        parser.error("--ticks must be >= 0")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
