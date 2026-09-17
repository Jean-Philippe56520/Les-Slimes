from __future__ import annotations

import argparse
import json
from datetime import datetime

from ..database.sqlite_repo import SQLiteRepository
from ..runtime.actors import ActorPermission
from .models import BudgetKind, JournalEntryType, PowerLevel, SanctionType
from .service import DivineGovernanceService, GovernanceAdminService


def _repo(args: argparse.Namespace) -> SQLiteRepository:
    return SQLiteRepository(args.db)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset")
    return parsed


def cmd_governance_status(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    actor_ids = [args.actor] if args.actor else ["father", "order", "chaos", "observer", "system"]
    result = [admin.status(actor_id) for actor_id in actor_ids]
    print(json.dumps(result[0] if args.actor else result, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_governance_budget(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    balance = admin.adjust_budget(
        args.actor,
        BudgetKind(args.kind),
        args.delta,
        reason=args.reason,
    )
    print(json.dumps({"actor_id": args.actor, "budget_kind": args.kind, "balance": balance}, indent=2))
    return 0


def cmd_governance_power(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    state = admin.set_power_level(
        args.actor,
        PowerLevel[args.level.upper()],
        reason=args.reason,
    )
    print(json.dumps({"actor_id": state.actor_id, "power_level": int(state.max_power_level), "power_name": state.max_power_level.name.lower()}, indent=2))
    return 0


def cmd_governance_permissions(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    actor = admin.set_permissions(
        args.actor,
        [ActorPermission(value) for value in args.permission],
        reason=args.reason,
    )
    print(json.dumps({"actor_id": actor.id, "permissions": sorted(actor.permissions)}, indent=2))
    return 0


def cmd_governance_active(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    actor = admin.set_active(
        args.actor,
        args.active == "true",
        reason=args.reason,
    )
    print(json.dumps({"actor_id": actor.id, "active": actor.active}, indent=2))
    return 0


def cmd_governance_sanction(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    parameters = json.loads(args.parameters) if args.parameters else None
    sanction = admin.impose_sanction(
        args.actor,
        SanctionType(args.type),
        reason=args.reason,
        parameters=parameters,
        expires_at_utc=_parse_datetime(args.expires_at),
    )
    print(json.dumps({"sanction_id": sanction.id, "actor_id": sanction.actor_id, "sanction_type": sanction.sanction_type.value}, indent=2))
    return 0


def cmd_governance_sanction_lift(args: argparse.Namespace) -> int:
    admin = GovernanceAdminService(_repo(args))
    sanction = admin.lift_sanction(args.id, reason=args.reason)
    print(json.dumps({"sanction_id": sanction.id, "lifted": sanction.lifted_at_utc is not None}, indent=2))
    return 0


def cmd_governance_journal(args: argparse.Namespace) -> int:
    service = DivineGovernanceService(_repo(args))
    entry_id = service.journal(
        args.actor,
        JournalEntryType(args.type),
        args.content,
        git_commit=args.git_commit,
    )
    print(json.dumps({"journal_entry_id": entry_id}, indent=2))
    return 0


def cmd_governance_proposal(args: argparse.Namespace) -> int:
    service = DivineGovernanceService(_repo(args))
    payload = json.loads(args.payload) if args.payload else {}
    proposal_id = service.propose(args.actor, args.type, args.title, payload)
    print(json.dumps({"proposal_id": proposal_id, "status": "proposed"}, indent=2))
    return 0


def register_governance_subcommands(sub: argparse._SubParsersAction) -> None:
    status = sub.add_parser("governance-status", help="Show persistent divine governance state")
    status.add_argument("--db", default="data/world.sqlite")
    status.add_argument("--actor", choices=["father", "order", "chaos", "observer", "system"])
    status.set_defaults(func=cmd_governance_status)

    budget = sub.add_parser("governance-budget", help="Adjust an actor budget as the Father")
    budget.add_argument("--db", default="data/world.sqlite")
    budget.add_argument("--actor", required=True)
    budget.add_argument("--kind", choices=[item.value for item in BudgetKind], required=True)
    budget.add_argument("--delta", type=int, required=True)
    budget.add_argument("--reason", required=True)
    budget.set_defaults(func=cmd_governance_budget)

    power = sub.add_parser("governance-power", help="Set an actor maximum power level as the Father")
    power.add_argument("--db", default="data/world.sqlite")
    power.add_argument("--actor", required=True)
    power.add_argument("--level", choices=[item.name.lower() for item in PowerLevel], required=True)
    power.add_argument("--reason", required=True)
    power.set_defaults(func=cmd_governance_power)

    permissions = sub.add_parser("governance-permission", help="Replace an actor permission set as the Father")
    permissions.add_argument("--db", default="data/world.sqlite")
    permissions.add_argument("--actor", required=True)
    permissions.add_argument("--permission", action="append", default=[])
    permissions.add_argument("--reason", required=True)
    permissions.set_defaults(func=cmd_governance_permissions)

    active = sub.add_parser("governance-active", help="Suspend or reactivate an actor as the Father")
    active.add_argument("--db", default="data/world.sqlite")
    active.add_argument("--actor", required=True)
    active.add_argument("--active", choices=["true", "false"], required=True)
    active.add_argument("--reason", required=True)
    active.set_defaults(func=cmd_governance_active)

    sanction = sub.add_parser("governance-sanction", help="Impose a declarative sanction as the Father")
    sanction.add_argument("--db", default="data/world.sqlite")
    sanction.add_argument("--actor", required=True)
    sanction.add_argument("--type", choices=[item.value for item in SanctionType], required=True)
    sanction.add_argument("--parameters", help="JSON object for sanction parameters")
    sanction.add_argument("--expires-at", help="ISO timestamp with timezone offset")
    sanction.add_argument("--reason", required=True)
    sanction.set_defaults(func=cmd_governance_sanction)

    lift = sub.add_parser("governance-sanction-lift", help="Lift a sanction as the Father")
    lift.add_argument("--db", default="data/world.sqlite")
    lift.add_argument("--id", type=int, required=True)
    lift.add_argument("--reason", required=True)
    lift.set_defaults(func=cmd_governance_sanction_lift)

    journal = sub.add_parser("governance-journal", help="Append a divine journal entry")
    journal.add_argument("--db", default="data/world.sqlite")
    journal.add_argument("--actor", required=True)
    journal.add_argument("--type", choices=[item.value for item in JournalEntryType], required=True)
    journal.add_argument("--content", required=True)
    journal.add_argument("--git-commit")
    journal.set_defaults(func=cmd_governance_journal)

    proposal = sub.add_parser("governance-proposal", help="Create a divine proposal without executing it")
    proposal.add_argument("--db", default="data/world.sqlite")
    proposal.add_argument("--actor", required=True)
    proposal.add_argument("--type", required=True)
    proposal.add_argument("--title", required=True)
    proposal.add_argument("--payload", help="JSON object", default="{}")
    proposal.set_defaults(func=cmd_governance_proposal)
