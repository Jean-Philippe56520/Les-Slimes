from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .analytics import build_world_report
from .config import WorldConfig
from .database.sqlite_repo import SQLiteRepository
from .experiments import create_experiment_fork, run_experiment_fork
from .observer import ObserverProposal, proposal_to_command
from .runtime import (
    CanonicalRuntime,
    CanonicalWorkerService,
    CanonicalWorldWorker,
    RuntimeStorage,
    WorkerServiceConfig,
)
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


def _health_dict(health) -> dict:
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
        "lag_seconds": round(health.lag_seconds, 6),
        "ticks_due": health.ticks_due,
        "pending_commands": health.pending_commands,
        "oldest_pending_command_utc": (
            health.oldest_pending_command_utc.isoformat()
            if health.oldest_pending_command_utc is not None
            else None
        ),
    }


def _idempotency(prefix: str, value: str | None) -> str:
    return value or f"cli:{prefix}:{uuid.uuid4().hex}"


def _enqueue(
    repo: SQLiteRepository,
    *,
    actor_id: str,
    command_type: str,
    payload: dict,
    idempotency_key: str,
    source_proposal_id: int | None = None,
) -> dict:
    command = RuntimeStorage(repo).enqueue_command(
        actor_id=actor_id,
        command_type=command_type,
        payload=payload,
        idempotency_key=idempotency_key,
        created_at_utc=datetime.now(UTC),
        source_proposal_id=source_proposal_id,
    )
    return {
        "command_id": command.id,
        "sequence": command.sequence,
        "status": command.status,
        "actor_id": command.actor_id,
        "command_type": command.command_type,
        "source_proposal_id": command.source_proposal_id,
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
    RuntimeStorage(repo)
    CanonicalRuntime(repo).ensure_initialized(datetime.now(UTC))
    print(json.dumps(_metrics_dict(world), indent=2))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    runtime = CanonicalRuntime(repo, batch_size=args.checkpoint or 1000)
    metadata = runtime.ensure_initialized(datetime.now(UTC))
    world = repo.load_world()
    target = metadata.last_simulated_at_utc + timedelta(
        seconds=world.config.tick_duration_seconds * args.ticks
    )
    result = CanonicalWorldWorker(
        repo,
        holder_id=args.holder_id,
        batch_size=args.checkpoint or 1000,
    ).run_until(target)
    print(
        json.dumps(
            {
                "commands_applied": result.commands_applied,
                "commands_rejected": result.commands_rejected,
                **_metrics_dict(repo.load_world()),
            },
            indent=2,
        )
    )
    return 0


def _worker_service(args: argparse.Namespace) -> CanonicalWorkerService:
    return CanonicalWorkerService(
        SQLiteRepository(args.db),
        holder_id=getattr(args, "holder_id", None),
        config=WorkerServiceConfig(
            poll_interval_seconds=args.poll_interval,
            lease_ttl_seconds=args.lease_ttl,
            heartbeat_interval_seconds=args.heartbeat_interval,
            batch_size=args.batch_size,
            command_page_size=args.command_page_size,
        ),
    )


def cmd_worker_run(args: argparse.Namespace) -> int:
    service = _worker_service(args)
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


def cmd_worker_status(args: argparse.Namespace) -> int:
    service = _worker_service(args)
    print(json.dumps(_health_dict(service.health()), indent=2))
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
    result = _enqueue(
        repo,
        actor_id=args.actor,
        command_type="deposit_food",
        payload={"x": args.x, "y": args.y, "count": args.count},
        idempotency_key=_idempotency("deposit-food", args.idempotency_key),
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_signal(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    payload = {"signal": args.signal, "x": args.x, "y": args.y}
    if args.radius is not None:
        payload["radius"] = args.radius
    result = _enqueue(
        repo,
        actor_id=args.actor,
        command_type="emit_signal",
        payload=payload,
        idempotency_key=_idempotency("signal", args.idempotency_key),
    )
    print(json.dumps(result, indent=2))
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
    row = repo.get_observer_proposal(args.id)
    proposal = ObserverProposal.from_dict(json.loads(row["proposal_json"]))
    converted = proposal_to_command(proposal)
    if converted is None:
        result = {
            "queued": False,
            "reason": "Analytical proposals do not mutate the world",
        }
        repo.update_observer_proposal(args.id, status="reviewed", result=result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    command_type, payload = converted
    result = _enqueue(
        repo,
        actor_id=args.actor,
        command_type=command_type,
        payload=payload,
        idempotency_key=_idempotency(f"proposal-{args.id}", args.idempotency_key),
        source_proposal_id=args.id,
    )
    repo.update_observer_proposal(
        args.id,
        status="queued",
        result={"command_id": result["command_id"], "approved_by": args.actor},
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_experiment_fork(args: argparse.Namespace) -> int:
    source = SQLiteRepository(args.db)
    _, manifest = create_experiment_fork(
        source,
        args.output,
        experiment_id=args.experiment_id,
        condition=args.condition,
        source_git_commit=args.source_git_commit,
        experiment_seed=args.experiment_seed,
        run_id=args.run_id,
    )
    print(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_experiment_run(args: argparse.Namespace) -> int:
    repo = SQLiteRepository(args.db)
    manifest = run_experiment_fork(repo, ticks=args.ticks)
    print(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _add_worker_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="data/world.sqlite")
    parser.add_argument("--holder-id")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--lease-ttl", type=float, default=30.0)
    parser.add_argument("--heartbeat-interval", type=float, default=10.0)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--command-page-size", type=int, default=1000)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="les-slimes")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a deterministic world")
    p_init.add_argument("--db", default="data/world.sqlite")
    p_init.add_argument("--config", default=str(_default_config_path()))
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_sim = sub.add_parser("simulate", help="Advance the canonical world through the worker")
    p_sim.add_argument("--db", default="data/world.sqlite")
    p_sim.add_argument("--ticks", type=int, required=True)
    p_sim.add_argument("--checkpoint", type=int, default=0)
    p_sim.add_argument("--holder-id", default="cli-worker")
    p_sim.set_defaults(func=cmd_simulate)

    p_worker = sub.add_parser("worker-run", help="Run the canonical world worker continuously")
    _add_worker_options(p_worker)
    p_worker.set_defaults(func=cmd_worker_run)

    p_worker_status = sub.add_parser("worker-status", help="Show canonical worker health")
    _add_worker_options(p_worker_status)
    p_worker_status.set_defaults(func=cmd_worker_status)

    p_status = sub.add_parser("status", help="Show current world state")
    p_status.add_argument("--db", default="data/world.sqlite")
    p_status.set_defaults(func=cmd_status)

    p_report = sub.add_parser("report", help="Build a structured emergence report")
    p_report.add_argument("--db", default="data/world.sqlite")
    p_report.add_argument("--output")
    p_report.set_defaults(func=cmd_report)

    p_food = sub.add_parser("deposit-food", help="Queue a food deposit")
    p_food.add_argument("--db", default="data/world.sqlite")
    p_food.add_argument("--actor", default="father")
    p_food.add_argument("--idempotency-key")
    p_food.add_argument("--x", type=float, required=True)
    p_food.add_argument("--y", type=float, required=True)
    p_food.add_argument("--count", type=int, default=1)
    p_food.set_defaults(func=cmd_deposit_food)

    p_signal = sub.add_parser("signal", help="Queue a learnable signal")
    p_signal.add_argument("--db", default="data/world.sqlite")
    p_signal.add_argument("--actor", default="father")
    p_signal.add_argument("--idempotency-key")
    p_signal.add_argument("--signal", choices=World.SIGNALS, required=True)
    p_signal.add_argument("--x", type=float, required=True)
    p_signal.add_argument("--y", type=float, required=True)
    p_signal.add_argument("--radius", type=float)
    p_signal.set_defaults(func=cmd_signal)

    p_prop_import = sub.add_parser("proposal-import", help="Import an Observer proposal JSON")
    p_prop_import.add_argument("--db", default="data/world.sqlite")
    p_prop_import.add_argument("--file", required=True)
    p_prop_import.set_defaults(func=cmd_proposal_import)

    p_prop_list = sub.add_parser("proposal-list", help="List Observer proposals")
    p_prop_list.add_argument("--db", default="data/world.sqlite")
    p_prop_list.add_argument("--status")
    p_prop_list.add_argument("--limit", type=int, default=100)
    p_prop_list.set_defaults(func=cmd_proposal_list)

    p_prop_apply = sub.add_parser("proposal-apply", help="Approve a proposal into the command queue")
    p_prop_apply.add_argument("--db", default="data/world.sqlite")
    p_prop_apply.add_argument("--id", type=int, required=True)
    p_prop_apply.add_argument("--actor", default="father")
    p_prop_apply.add_argument("--idempotency-key")
    p_prop_apply.set_defaults(func=cmd_proposal_apply)

    p_exp_fork = sub.add_parser(
        "experiment-fork",
        help="Create an isolated non-canonical fork from the canonical world",
    )
    p_exp_fork.add_argument("--db", default="data/world.sqlite")
    p_exp_fork.add_argument("--output", required=True)
    p_exp_fork.add_argument("--experiment-id", required=True)
    p_exp_fork.add_argument("--condition", required=True)
    p_exp_fork.add_argument("--source-git-commit", required=True)
    p_exp_fork.add_argument("--experiment-seed", type=int)
    p_exp_fork.add_argument("--run-id")
    p_exp_fork.set_defaults(func=cmd_experiment_fork)

    p_exp_run = sub.add_parser(
        "experiment-run",
        help="Advance an isolated non-canonical experiment fork",
    )
    p_exp_run.add_argument("--db", required=True)
    p_exp_run.add_argument("--ticks", type=int, required=True)
    p_exp_run.set_defaults(func=cmd_experiment_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "ticks", 0) < 0:
        parser.error("--ticks must be >= 0")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
