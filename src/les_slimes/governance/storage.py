from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from ..database.scope import ensure_canonical_scope
from ..database.sqlite_repo import SQLiteRepository
from .models import (
    BudgetKind,
    DivineActorState,
    DivineIntervention,
    DivineSanction,
    JournalEntryType,
    PowerLevel,
    SanctionType,
)


GOVERNANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS divine_actor_state (
    actor_id TEXT PRIMARY KEY,
    max_power_level INTEGER NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS divine_budget_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    budget_kind TEXT NOT NULL,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    intervention_id TEXT,
    created_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_divine_budget_actor_kind
ON divine_budget_ledger(actor_id, budget_kind, id);

CREATE TABLE IF NOT EXISTS divine_sanctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    sanction_type TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    imposed_by TEXT NOT NULL,
    starts_at_utc TEXT NOT NULL,
    expires_at_utc TEXT,
    lifted_at_utc TEXT,
    lifted_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_divine_sanctions_actor
ON divine_sanctions(actor_id, id);

CREATE TABLE IF NOT EXISTS divine_interventions (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    action_kind TEXT NOT NULL,
    power_level INTEGER NOT NULL,
    permission TEXT NOT NULL,
    command_id TEXT UNIQUE,
    source_proposal_id INTEGER,
    status TEXT NOT NULL,
    budget_kind TEXT,
    budget_cost INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    authorized_at_utc TEXT,
    executed_at_utc TEXT,
    rejected_reason TEXT,
    git_branch TEXT,
    git_pr TEXT,
    git_commit TEXT
);
CREATE INDEX IF NOT EXISTS idx_divine_interventions_actor
ON divine_interventions(actor_id, created_at_utc);

CREATE TABLE IF NOT EXISTS divine_journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    world_tick INTEGER,
    intervention_id TEXT,
    git_commit TEXT,
    content TEXT NOT NULL,
    context_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS divine_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    created_at_utc TEXT NOT NULL,
    decided_at_utc TEXT,
    decided_by TEXT,
    decision_reason TEXT
);

CREATE TABLE IF NOT EXISTS divine_audit_log (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    previous_hash TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    subject_actor_id TEXT,
    payload_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    entry_hash TEXT NOT NULL UNIQUE
);
"""


class GovernanceStorage:
    def __init__(self, repository: SQLiteRepository) -> None:
        ensure_canonical_scope(repository)
        self.repository = repository
        self.initialize_schema()

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Governance timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @classmethod
    def _parse_dt(cls, value: str | None) -> datetime | None:
        if value is None:
            return None
        return cls._utc(datetime.fromisoformat(value))

    def initialize_schema(self) -> None:
        self.repository.initialize_schema()
        now = datetime.now(UTC).isoformat()
        with self.repository._connect() as conn:
            conn.executescript(GOVERNANCE_SCHEMA)
            defaults = (
                ("father", int(PowerLevel.TRANSGRESSION)),
                ("order", int(PowerLevel.OBSERVATION)),
                ("chaos", int(PowerLevel.OBSERVATION)),
                ("observer", int(PowerLevel.OBSERVATION)),
                ("system", int(PowerLevel.OBSERVATION)),
            )
            for actor_id, power in defaults:
                conn.execute(
                    """
                    INSERT INTO divine_actor_state(actor_id, max_power_level, updated_at_utc)
                    VALUES (?, ?, ?) ON CONFLICT(actor_id) DO NOTHING
                    """,
                    (actor_id, power, now),
                )
            conn.commit()

    def get_actor_state(self, actor_id: str) -> DivineActorState:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_actor_state WHERE actor_id = ?", (actor_id,)
            ).fetchone()
        if row is None:
            raise KeyError(actor_id)
        return DivineActorState(
            actor_id=str(row["actor_id"]),
            max_power_level=PowerLevel(int(row["max_power_level"])),
            updated_at_utc=self._parse_dt(row["updated_at_utc"]),  # type: ignore[arg-type]
        )

    def set_power_level(
        self,
        actor_id: str,
        power_level: PowerLevel,
        *,
        performed_by: str,
        reason: str,
        now_utc: datetime,
    ) -> DivineActorState:
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO divine_actor_state(actor_id, max_power_level, updated_at_utc)
                VALUES (?, ?, ?)
                ON CONFLICT(actor_id) DO UPDATE SET
                    max_power_level = excluded.max_power_level,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (actor_id, int(power_level), now.isoformat()),
            )
            self.append_audit_in_transaction(
                conn,
                event_type="power_level_set",
                actor_id=performed_by,
                subject_actor_id=actor_id,
                payload={"power_level": int(power_level), "reason": reason},
                created_at_utc=now,
            )
            conn.commit()
        return self.get_actor_state(actor_id)

    def budget_balance(self, actor_id: str, kind: BudgetKind) -> int:
        with self.repository._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(delta), 0) AS balance
                FROM divine_budget_ledger WHERE actor_id = ? AND budget_kind = ?
                """,
                (actor_id, kind.value),
            ).fetchone()
        return int(row["balance"])

    def budget_balance_in_transaction(
        self, conn: sqlite3.Connection, actor_id: str, kind: BudgetKind
    ) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(delta), 0) AS balance
            FROM divine_budget_ledger WHERE actor_id = ? AND budget_kind = ?
            """,
            (actor_id, kind.value),
        ).fetchone()
        return int(row["balance"])

    def adjust_budget(
        self,
        actor_id: str,
        kind: BudgetKind,
        delta: int,
        *,
        performed_by: str,
        reason: str,
        now_utc: datetime,
    ) -> int:
        if delta == 0:
            raise ValueError("Budget delta must be non-zero")
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO divine_budget_ledger(
                    actor_id, budget_kind, delta, reason, performed_by, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (actor_id, kind.value, delta, reason, performed_by, now.isoformat()),
            )
            self.append_audit_in_transaction(
                conn,
                event_type="budget_adjusted",
                actor_id=performed_by,
                subject_actor_id=actor_id,
                payload={"budget_kind": kind.value, "delta": delta, "reason": reason},
                created_at_utc=now,
            )
            conn.commit()
        return self.budget_balance(actor_id, kind)

    def active_sanctions(
        self, actor_id: str, *, now_utc: datetime
    ) -> list[DivineSanction]:
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM divine_sanctions
                WHERE actor_id = ? AND starts_at_utc <= ? AND lifted_at_utc IS NULL
                  AND (expires_at_utc IS NULL OR expires_at_utc > ?)
                ORDER BY id ASC
                """,
                (actor_id, now.isoformat(), now.isoformat()),
            ).fetchall()
        return [self._row_to_sanction(row) for row in rows]

    def impose_sanction(
        self,
        actor_id: str,
        sanction_type: SanctionType,
        *,
        parameters: dict[str, Any] | None,
        reason: str,
        imposed_by: str,
        starts_at_utc: datetime,
        expires_at_utc: datetime | None = None,
    ) -> DivineSanction:
        starts = self._utc(starts_at_utc)
        expires = self._utc(expires_at_utc) if expires_at_utc else None
        if expires is not None and expires <= starts:
            raise ValueError("Sanction expiry must be after start")
        payload = parameters or {}
        if sanction_type == SanctionType.MAX_POWER_LEVEL:
            level = payload.get("power_level")
            if not isinstance(level, int) or level not in {1, 2, 3, 4, 5}:
                raise ValueError("MAX_POWER_LEVEL requires parameters.power_level 1..5")
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                INSERT INTO divine_sanctions(
                    actor_id, sanction_type, parameters_json, reason, imposed_by,
                    starts_at_utc, expires_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    sanction_type.value,
                    json.dumps(payload, sort_keys=True),
                    reason,
                    imposed_by,
                    starts.isoformat(),
                    expires.isoformat() if expires else None,
                ),
            )
            sanction_id = int(cursor.lastrowid)
            self.append_audit_in_transaction(
                conn,
                event_type="sanction_imposed",
                actor_id=imposed_by,
                subject_actor_id=actor_id,
                payload={
                    "sanction_id": sanction_id,
                    "sanction_type": sanction_type.value,
                    "parameters": payload,
                    "reason": reason,
                    "expires_at_utc": expires.isoformat() if expires else None,
                },
                created_at_utc=starts,
            )
            conn.commit()
        return self.get_sanction(sanction_id)

    def get_sanction(self, sanction_id: int) -> DivineSanction:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_sanctions WHERE id = ?", (sanction_id,)
            ).fetchone()
        if row is None:
            raise KeyError(sanction_id)
        return self._row_to_sanction(row)

    def lift_sanction(
        self,
        sanction_id: int,
        *,
        lifted_by: str,
        reason: str,
        now_utc: datetime,
    ) -> DivineSanction:
        now = self._utc(now_utc)
        sanction = self.get_sanction(sanction_id)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE divine_sanctions SET lifted_at_utc = ?, lifted_by = ?
                WHERE id = ? AND lifted_at_utc IS NULL
                """,
                (now.isoformat(), lifted_by, sanction_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Sanction is already lifted")
            self.append_audit_in_transaction(
                conn,
                event_type="sanction_lifted",
                actor_id=lifted_by,
                subject_actor_id=sanction.actor_id,
                payload={"sanction_id": sanction_id, "reason": reason},
                created_at_utc=now,
            )
            conn.commit()
        return self.get_sanction(sanction_id)

    def get_intervention_for_command(self, command_id: str) -> DivineIntervention | None:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_interventions WHERE command_id = ?", (command_id,)
            ).fetchone()
        return self._row_to_intervention(row) if row else None

    def create_intervention(
        self,
        *,
        actor_id: str,
        action_kind: str,
        power_level: PowerLevel,
        permission: str,
        command_id: str | None,
        source_proposal_id: int | None,
        status: str,
        budget_kind: BudgetKind | None,
        budget_cost: int,
        reason: str,
        now_utc: datetime,
    ) -> DivineIntervention:
        now = self._utc(now_utc)
        intervention_id = f"INT-{uuid.uuid4().hex}"
        with self.repository._connect() as conn:
            conn.execute(
                """
                INSERT INTO divine_interventions(
                    id, actor_id, action_kind, power_level, permission, command_id,
                    source_proposal_id, status, budget_kind, budget_cost, reason, created_at_utc,
                    authorized_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intervention_id,
                    actor_id,
                    action_kind,
                    int(power_level),
                    permission,
                    command_id,
                    source_proposal_id,
                    status,
                    budget_kind.value if budget_kind else None,
                    budget_cost,
                    reason,
                    now.isoformat(),
                    now.isoformat() if status == "authorized" else None,
                ),
            )
            conn.commit()
        return self.get_intervention(intervention_id)

    def get_intervention(self, intervention_id: str) -> DivineIntervention:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
        if row is None:
            raise KeyError(intervention_id)
        return self._row_to_intervention(row)

    def reject_intervention(
        self, intervention_id: str, *, reason: str, now_utc: datetime
    ) -> None:
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT actor_id FROM divine_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
            if row is None:
                raise KeyError(intervention_id)
            conn.execute(
                """
                UPDATE divine_interventions
                SET status = 'rejected', rejected_reason = ? WHERE id = ?
                """,
                (reason, intervention_id),
            )
            self.append_audit_in_transaction(
                conn,
                event_type="intervention_rejected",
                actor_id=str(row["actor_id"]),
                subject_actor_id=str(row["actor_id"]),
                payload={"intervention_id": intervention_id, "reason": reason},
                created_at_utc=now,
            )
            conn.commit()

    def execute_intervention_in_transaction(
        self,
        conn: sqlite3.Connection,
        *,
        intervention: DivineIntervention,
        now_utc: datetime,
        father_unlimited: bool,
    ) -> None:
        now = self._utc(now_utc)
        existing = conn.execute(
            "SELECT status FROM divine_interventions WHERE id = ?", (intervention.id,)
        ).fetchone()
        if existing is None:
            raise KeyError(intervention.id)
        if existing["status"] == "executed":
            return
        if intervention.budget_kind is not None and intervention.budget_cost > 0 and not father_unlimited:
            balance = self.budget_balance_in_transaction(
                conn, intervention.actor_id, intervention.budget_kind
            )
            if balance < intervention.budget_cost:
                raise PermissionError("Insufficient governance budget at commit time")
            conn.execute(
                """
                INSERT INTO divine_budget_ledger(
                    actor_id, budget_kind, delta, reason, performed_by,
                    intervention_id, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intervention.actor_id,
                    intervention.budget_kind.value,
                    -intervention.budget_cost,
                    f"Execution of {intervention.action_kind}",
                    intervention.actor_id,
                    intervention.id,
                    now.isoformat(),
                ),
            )
        conn.execute(
            """
            UPDATE divine_interventions
            SET status = 'executed', executed_at_utc = ? WHERE id = ?
            """,
            (now.isoformat(), intervention.id),
        )
        self.append_audit_in_transaction(
            conn,
            event_type="intervention_executed",
            actor_id=intervention.actor_id,
            subject_actor_id=intervention.actor_id,
            payload={
                "intervention_id": intervention.id,
                "command_id": intervention.command_id,
                "action_kind": intervention.action_kind,
                "budget_kind": intervention.budget_kind.value if intervention.budget_kind else None,
                "budget_cost": intervention.budget_cost,
            },
            created_at_utc=now,
        )

    def add_journal_entry(
        self,
        *,
        actor_id: str,
        entry_type: JournalEntryType,
        content: str,
        now_utc: datetime,
        world_tick: int | None = None,
        intervention_id: str | None = None,
        git_commit: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> int:
        if not content.strip():
            raise ValueError("Journal content is required")
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO divine_journal_entries(
                    actor_id, entry_type, world_tick, intervention_id, git_commit,
                    content, context_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    entry_type.value,
                    world_tick,
                    intervention_id,
                    git_commit,
                    content,
                    json.dumps(context or {}, sort_keys=True),
                    now.isoformat(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def create_proposal(
        self,
        *,
        actor_id: str,
        proposal_type: str,
        title: str,
        payload: dict[str, Any],
        now_utc: datetime,
    ) -> int:
        if not proposal_type.strip() or not title.strip():
            raise ValueError("proposal_type and title are required")
        now = self._utc(now_utc)
        with self.repository._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO divine_proposals(
                    actor_id, proposal_type, title, payload_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    proposal_type,
                    title,
                    json.dumps(payload, sort_keys=True),
                    now.isoformat(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def append_audit_in_transaction(
        self,
        conn: sqlite3.Connection,
        *,
        event_type: str,
        actor_id: str,
        subject_actor_id: str | None,
        payload: dict[str, Any],
        created_at_utc: datetime,
    ) -> str:
        now = self._utc(created_at_utc)
        row = conn.execute(
            "SELECT entry_hash FROM divine_audit_log ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(row["entry_hash"]) if row else "GENESIS"
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        material = "|".join(
            [previous_hash, event_type, actor_id, subject_actor_id or "", payload_json, now.isoformat()]
        )
        entry_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        conn.execute(
            """
            INSERT INTO divine_audit_log(
                previous_hash, event_type, actor_id, subject_actor_id,
                payload_json, created_at_utc, entry_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                previous_hash,
                event_type,
                actor_id,
                subject_actor_id,
                payload_json,
                now.isoformat(),
                entry_hash,
            ),
        )
        return entry_hash

    def validate_audit_chain(self) -> bool:
        previous = "GENESIS"
        with self.repository._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM divine_audit_log ORDER BY sequence ASC"
            ).fetchall()
        for row in rows:
            if str(row["previous_hash"]) != previous:
                return False
            material = "|".join(
                [
                    previous,
                    str(row["event_type"]),
                    str(row["actor_id"]),
                    str(row["subject_actor_id"] or ""),
                    str(row["payload_json"]),
                    str(row["created_at_utc"]),
                ]
            )
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if expected != str(row["entry_hash"]):
                return False
            previous = expected
        return True

    def _row_to_sanction(self, row: sqlite3.Row) -> DivineSanction:
        return DivineSanction(
            id=int(row["id"]),
            actor_id=str(row["actor_id"]),
            sanction_type=SanctionType(str(row["sanction_type"])),
            parameters=json.loads(row["parameters_json"]),
            reason=str(row["reason"]),
            imposed_by=str(row["imposed_by"]),
            starts_at_utc=self._parse_dt(row["starts_at_utc"]),  # type: ignore[arg-type]
            expires_at_utc=self._parse_dt(row["expires_at_utc"]),
            lifted_at_utc=self._parse_dt(row["lifted_at_utc"]),
            lifted_by=str(row["lifted_by"]) if row["lifted_by"] else None,
        )

    def _row_to_intervention(self, row: sqlite3.Row) -> DivineIntervention:
        return DivineIntervention(
            id=str(row["id"]),
            actor_id=str(row["actor_id"]),
            action_kind=str(row["action_kind"]),
            power_level=PowerLevel(int(row["power_level"])),
            permission=str(row["permission"]),
            command_id=str(row["command_id"]) if row["command_id"] else None,
            source_proposal_id=(
                int(row["source_proposal_id"]) if row["source_proposal_id"] is not None else None
            ),
            status=str(row["status"]),
            budget_kind=BudgetKind(str(row["budget_kind"])) if row["budget_kind"] else None,
            budget_cost=int(row["budget_cost"]),
            reason=str(row["reason"]),
            created_at_utc=self._parse_dt(row["created_at_utc"]),  # type: ignore[arg-type]
            authorized_at_utc=self._parse_dt(row["authorized_at_utc"]),
            executed_at_utc=self._parse_dt(row["executed_at_utc"]),
            rejected_reason=str(row["rejected_reason"]) if row["rejected_reason"] else None,
            git_branch=str(row["git_branch"]) if row["git_branch"] else None,
            git_pr=str(row["git_pr"]) if row["git_pr"] else None,
            git_commit=str(row["git_commit"]) if row["git_commit"] else None,
        )
