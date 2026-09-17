from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any


class PowerLevel(IntEnum):
    OBSERVATION = 1
    MIRACLE = 2
    DECREE = 3
    LAW = 4
    TRANSGRESSION = 5


class BudgetKind(StrEnum):
    MIRACLE = "miracle"
    LEGISLATIVE = "legislative"
    FAVOR = "favor"
    TRANSGRESSION_DEBT = "transgression_debt"


class SanctionType(StrEnum):
    SUSPEND = "suspend"
    DENY_MIRACLE = "deny_miracle"
    DENY_DECREE = "deny_decree"
    FREEZE_MIRACLE_BUDGET = "freeze_miracle_budget"
    FREEZE_LEGISLATIVE_BUDGET = "freeze_legislative_budget"
    MAX_POWER_LEVEL = "max_power_level"


class JournalEntryType(StrEnum):
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    DECISION = "decision"
    ARGUMENT = "argument"
    RESULT = "result"
    POSTMORTEM = "postmortem"
    COUNCIL = "council"


@dataclass(frozen=True, slots=True)
class DivineActorState:
    actor_id: str
    max_power_level: PowerLevel
    updated_at_utc: datetime


@dataclass(frozen=True, slots=True)
class DivineSanction:
    id: int
    actor_id: str
    sanction_type: SanctionType
    parameters: dict[str, Any]
    reason: str
    imposed_by: str
    starts_at_utc: datetime
    expires_at_utc: datetime | None
    lifted_at_utc: datetime | None
    lifted_by: str | None


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    actor_id: str
    required_power_level: PowerLevel
    effective_power_level: PowerLevel
    permission: str
    budget_kind: BudgetKind | None
    budget_cost: int
    budget_available: int | None
    active_sanctions: tuple[SanctionType, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class DivineIntervention:
    id: str
    actor_id: str
    action_kind: str
    power_level: PowerLevel
    permission: str
    command_id: str | None
    source_proposal_id: int | None
    status: str
    budget_kind: BudgetKind | None
    budget_cost: int
    reason: str
    created_at_utc: datetime
    authorized_at_utc: datetime | None
    executed_at_utc: datetime | None
    rejected_reason: str | None
    git_branch: str | None
    git_pr: str | None
    git_commit: str | None
