from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from ..runtime.actors import ActorPermission
from ..runtime.commands import get_command_definition
from ..runtime.storage import RuntimeCommand, RuntimeStorage
from .models import AuthorizationDecision, BudgetKind, PowerLevel, SanctionType
from .storage import GovernanceStorage


class GovernancePolicy:
    def __init__(self, runtime: RuntimeStorage, governance: GovernanceStorage) -> None:
        self.runtime = runtime
        self.governance = governance

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Governance timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def authorize(self, command: RuntimeCommand, *, now_utc: datetime) -> AuthorizationDecision:
        now = self._utc(now_utc)
        definition = get_command_definition(command.command_type)
        actor = self.runtime.get_actor(command.actor_id)
        state = self.governance.get_actor_state(command.actor_id)
        sanctions = self.governance.active_sanctions(command.actor_id, now_utc=now)
        active_types = tuple(s.sanction_type for s in sanctions)
        effective_power = self._effective_power(state.max_power_level, sanctions)
        budget_available = None if command.actor_id == "father" else self.governance.budget_balance(
            command.actor_id, definition.budget_kind
        )

        if not actor.active:
            return self._decision(False, command, effective_power, budget_available, active_types, "Actor is inactive")
        if SanctionType.SUSPEND in active_types:
            return self._decision(False, command, effective_power, budget_available, active_types, "Actor is suspended")
        if not actor.can(definition.permission):
            return self._decision(False, command, effective_power, budget_available, active_types, "Required technical permission is missing")
        if command.source_proposal_id is not None and not actor.can(ActorPermission.APPLY_OBSERVER_PROPOSAL):
            return self._decision(False, command, effective_power, budget_available, active_types, "Observer proposal approval permission is missing")
        if effective_power < definition.power_level:
            return self._decision(False, command, effective_power, budget_available, active_types, "Power level is insufficient")
        if definition.power_level == PowerLevel.MIRACLE and SanctionType.DENY_MIRACLE in active_types:
            return self._decision(False, command, effective_power, budget_available, active_types, "Miracles are denied by sanction")
        if definition.power_level == PowerLevel.DECREE and SanctionType.DENY_DECREE in active_types:
            return self._decision(False, command, effective_power, budget_available, active_types, "Decrees are denied by sanction")
        if definition.budget_kind == BudgetKind.MIRACLE and SanctionType.FREEZE_MIRACLE_BUDGET in active_types:
            return self._decision(False, command, effective_power, budget_available, active_types, "Miracle budget is frozen")
        if definition.budget_kind == BudgetKind.LEGISLATIVE and SanctionType.FREEZE_LEGISLATIVE_BUDGET in active_types:
            return self._decision(False, command, effective_power, budget_available, active_types, "Legislative budget is frozen")
        if command.actor_id != "father" and (budget_available or 0) < definition.budget_cost:
            return self._decision(False, command, effective_power, budget_available, active_types, "Governance budget is insufficient")
        return self._decision(True, command, effective_power, budget_available, active_types, "authorized")

    def assert_authorized_in_transaction(
        self,
        conn: sqlite3.Connection,
        command: RuntimeCommand,
        *,
        now_utc: datetime,
    ) -> None:
        now = self._utc(now_utc)
        definition = get_command_definition(command.command_type)
        actor_row = conn.execute(
            "SELECT permissions_json, active FROM runtime_actors WHERE id = ?", (command.actor_id,)
        ).fetchone()
        if actor_row is None:
            raise PermissionError("Actor no longer exists")
        if not bool(actor_row["active"]):
            raise PermissionError("Actor became inactive before commit")
        permissions = set(json.loads(actor_row["permissions_json"]))
        if definition.permission.value not in permissions:
            raise PermissionError("Required permission was revoked before commit")
        if command.source_proposal_id is not None and ActorPermission.APPLY_OBSERVER_PROPOSAL.value not in permissions:
            raise PermissionError("Observer proposal approval permission was revoked before commit")

        state = conn.execute(
            "SELECT max_power_level FROM divine_actor_state WHERE actor_id = ?", (command.actor_id,)
        ).fetchone()
        if state is None:
            raise PermissionError("Governance actor state disappeared before commit")
        sanctions = conn.execute(
            """
            SELECT sanction_type, parameters_json FROM divine_sanctions
            WHERE actor_id = ? AND starts_at_utc <= ? AND lifted_at_utc IS NULL
              AND (expires_at_utc IS NULL OR expires_at_utc > ?)
            """,
            (command.actor_id, now.isoformat(), now.isoformat()),
        ).fetchall()
        sanction_types = {SanctionType(str(row["sanction_type"])) for row in sanctions}
        effective_power = PowerLevel(int(state["max_power_level"]))
        for row in sanctions:
            if SanctionType(str(row["sanction_type"])) == SanctionType.MAX_POWER_LEVEL:
                params = json.loads(row["parameters_json"])
                effective_power = min(effective_power, PowerLevel(int(params["power_level"])))
        if SanctionType.SUSPEND in sanction_types:
            raise PermissionError("Actor was suspended before commit")
        if effective_power < definition.power_level:
            raise PermissionError("Power level became insufficient before commit")
        if definition.power_level == PowerLevel.MIRACLE and SanctionType.DENY_MIRACLE in sanction_types:
            raise PermissionError("Miracles were denied before commit")
        if definition.power_level == PowerLevel.DECREE and SanctionType.DENY_DECREE in sanction_types:
            raise PermissionError("Decrees were denied before commit")
        if definition.budget_kind == BudgetKind.MIRACLE and SanctionType.FREEZE_MIRACLE_BUDGET in sanction_types:
            raise PermissionError("Miracle budget was frozen before commit")
        if definition.budget_kind == BudgetKind.LEGISLATIVE and SanctionType.FREEZE_LEGISLATIVE_BUDGET in sanction_types:
            raise PermissionError("Legislative budget was frozen before commit")
        if command.actor_id != "father":
            balance = self.governance.budget_balance_in_transaction(conn, command.actor_id, definition.budget_kind)
            if balance < definition.budget_cost:
                raise PermissionError("Governance budget became insufficient before commit")

    @staticmethod
    def _effective_power(base: PowerLevel, sanctions) -> PowerLevel:
        effective = base
        for sanction in sanctions:
            if sanction.sanction_type == SanctionType.MAX_POWER_LEVEL:
                effective = min(effective, PowerLevel(int(sanction.parameters["power_level"])))
        return effective

    @staticmethod
    def _decision(
        allowed: bool,
        command: RuntimeCommand,
        effective_power: PowerLevel,
        budget_available: int | None,
        sanctions: tuple[SanctionType, ...],
        reason: str,
    ) -> AuthorizationDecision:
        definition = get_command_definition(command.command_type)
        return AuthorizationDecision(
            allowed=allowed,
            actor_id=command.actor_id,
            required_power_level=definition.power_level,
            effective_power_level=effective_power,
            permission=definition.permission.value,
            budget_kind=definition.budget_kind,
            budget_cost=definition.budget_cost,
            budget_available=budget_available,
            active_sanctions=sanctions,
            reason=reason,
        )
