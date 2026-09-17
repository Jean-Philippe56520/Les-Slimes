from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from ..database.base import RelationalRepository
from ..governance.models import BudgetKind, PowerLevel, SanctionType
from ..governance.storage import GovernanceStorage
from ..runtime.storage import RuntimeStorage
from .access import AUTHORIZED_REPOSITORY
from .git_gateway import CreatorGitGateway, GitProvider, PullRequestSnapshot
from .legislation import LAW_BUDGET_COST, DivineLegislationService, LegislativeStatus
from .sovereign import MergeAuthorization


@dataclass(frozen=True, slots=True)
class PromulgationResult:
    proposal_id: int
    merge_commit_sha: str
    reconciled: bool


class PromulgationBlocked(PermissionError):
    pass


class CreatorPromulgationService:
    """Saga that turns one accepted divine Law into an audited merge on main.

    GitHub and the canonical database cannot share one transaction. The service therefore
    reserves legislative budget before the external merge and records an explicit
    prepared/uncertain/completed state in the law dossier. Unknown merge outcomes keep
    the reservation until the next reconciliation instead of refunding speculatively.
    """

    def __init__(self, repository: RelationalRepository, provider: GitProvider) -> None:
        self.repository = repository
        self.git = CreatorGitGateway(provider)
        self.legislation = DivineLegislationService(repository)
        self.runtime = RuntimeStorage(repository)
        self.governance = GovernanceStorage(repository)  # type: ignore[arg-type]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _governance_valid(self, actor_id: str, *, require_budget: bool) -> bool:
        actor = self.runtime.get_actor(actor_id)
        if not actor.active:
            return False
        state = self.governance.get_actor_state(actor_id)
        sanctions = self.governance.active_sanctions(actor_id, now_utc=self._now())
        types = {sanction.sanction_type for sanction in sanctions}
        if SanctionType.SUSPEND in types:
            return False
        if SanctionType.FREEZE_LEGISLATIVE_BUDGET in types:
            return False
        effective = state.max_power_level
        for sanction in sanctions:
            if sanction.sanction_type == SanctionType.MAX_POWER_LEVEL:
                effective = min(
                    effective,
                    PowerLevel(int(sanction.parameters["power_level"])),
                )
        if effective < PowerLevel.LAW:
            return False
        if require_budget:
            return (
                self.governance.budget_balance(actor_id, BudgetKind.LEGISLATIVE)
                >= LAW_BUDGET_COST
            )
        return True

    def _authorization_from_dossier(self, stored: dict) -> MergeAuthorization:
        if stored["status"] != LegislativeStatus.ACCEPTED.value:
            raise PromulgationBlocked("Only an accepted Law may be promulgated")
        payload = stored["payload"]
        review = payload.get("last_review") or {}
        if review.get("decision") != "accept" or review.get("blockers") not in ([], ()):
            raise PromulgationBlocked("Persisted Creator review does not authorize merge")
        return MergeAuthorization(
            repository_full_name=AUTHORIZED_REPOSITORY,
            pr_number=int(payload["pr_number"]),
            expected_head_sha=str(payload["head_sha"]),
            expected_base_sha=str(payload["base_sha"]),
            candidate_actor_id=str(stored["actor_id"]),
            proposal_id=int(stored["id"]),
        )

    @staticmethod
    def _promulgation_state(stored: dict) -> dict:
        value = stored["payload"].get("promulgation")
        return dict(value) if isinstance(value, dict) else {}

    def _preflight_blockers(
        self,
        stored: dict,
        authorization: MergeAuthorization,
        snapshot: PullRequestSnapshot,
        *,
        require_budget: bool,
    ) -> tuple[str, ...]:
        payload = stored["payload"]
        blockers: list[str] = []
        if snapshot.number != authorization.pr_number:
            blockers.append("pull request number changed")
        if snapshot.head_branch != payload["branch"]:
            blockers.append("pull request head branch changed")
        if snapshot.head_sha != authorization.expected_head_sha:
            blockers.append("pull request head SHA changed after Creator review")
        if snapshot.base_branch != "main":
            blockers.append("pull request no longer targets main")
        main_sha = self.git.main_sha()
        if main_sha != authorization.expected_base_sha:
            blockers.append("main changed after Creator review")
        if snapshot.base_sha != authorization.expected_base_sha:
            blockers.append("pull request base SHA changed after Creator review")
        if not snapshot.merged:
            if snapshot.state != "open":
                blockers.append("pull request is not open")
            if not snapshot.mergeable:
                blockers.append("pull request is not mergeable")
            passed = self.git.passed_checks(authorization.expected_head_sha)
            missing = sorted(set(payload["required_checks"]) - set(passed))
            if missing:
                blockers.append("required checks not passed: " + ", ".join(missing))
        if not self._governance_valid(
            authorization.candidate_actor_id,
            require_budget=require_budget,
        ):
            blockers.append("Law is no longer eligible under current governance")
        return tuple(blockers)

    def _reserve_budget(self, stored: dict, authorization: MergeAuthorization) -> None:
        proposal_id = authorization.proposal_id
        actor_id = authorization.candidate_actor_id
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            row = conn.execute(
                "SELECT status, payload_json FROM divine_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if str(row["status"]) != LegislativeStatus.ACCEPTED.value:
                raise PromulgationBlocked("Law ceased to be accepted before reservation")
            payload = json.loads(row["payload_json"])
            previous = payload.get("promulgation") or {}
            if previous.get("state") in {"prepared", "uncertain"}:
                conn.commit()
                return
            attempt = int(previous.get("attempt", 0)) + 1
            intervention_id = f"LAW-{proposal_id}-A{attempt}"
            balance_row = conn.execute(
                """
                SELECT COALESCE(SUM(delta), 0) AS balance
                FROM divine_budget_ledger
                WHERE actor_id = ? AND budget_kind = ?
                """,
                (actor_id, BudgetKind.LEGISLATIVE.value),
            ).fetchone()
            if int(balance_row["balance"]) < LAW_BUDGET_COST:
                raise PromulgationBlocked("Legislative budget became insufficient")
            conn.execute(
                """
                INSERT INTO divine_budget_ledger(
                    actor_id, budget_kind, delta, reason, performed_by,
                    intervention_id, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    BudgetKind.LEGISLATIVE.value,
                    -LAW_BUDGET_COST,
                    f"Reservation for Law proposal {proposal_id}",
                    "father",
                    intervention_id,
                    now.isoformat(),
                ),
            )
            payload["promulgation"] = {
                "state": "prepared",
                "attempt": attempt,
                "intervention_id": intervention_id,
                "expected_head_sha": authorization.expected_head_sha,
                "expected_base_sha": authorization.expected_base_sha,
                "prepared_at_utc": now.isoformat(),
            }
            conn.execute(
                "UPDATE divine_proposals SET payload_json = ? WHERE id = ?",
                (json.dumps(payload, sort_keys=True), proposal_id),
            )
            self.governance.append_audit_in_transaction(
                conn,
                event_type="law_promulgation_prepared",
                actor_id="father",
                subject_actor_id=actor_id,
                payload={
                    "proposal_id": proposal_id,
                    "attempt": attempt,
                    "intervention_id": intervention_id,
                    "head_sha": authorization.expected_head_sha,
                    "base_sha": authorization.expected_base_sha,
                },
                created_at_utc=now,
            )
            conn.commit()

    def _set_uncertain(self, proposal_id: int, *, reason: str) -> None:
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            row = conn.execute(
                "SELECT actor_id, status, payload_json FROM divine_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if str(row["status"]) != LegislativeStatus.ACCEPTED.value:
                conn.commit()
                return
            payload = json.loads(row["payload_json"])
            state = payload.get("promulgation") or {}
            if state.get("state") == "prepared":
                state["state"] = "uncertain"
                state["uncertain_reason"] = reason
                state["uncertain_at_utc"] = now.isoformat()
                payload["promulgation"] = state
                conn.execute(
                    "UPDATE divine_proposals SET payload_json = ? WHERE id = ?",
                    (json.dumps(payload, sort_keys=True), proposal_id),
                )
                self.governance.append_audit_in_transaction(
                    conn,
                    event_type="law_promulgation_uncertain",
                    actor_id="father",
                    subject_actor_id=str(row["actor_id"]),
                    payload={"proposal_id": proposal_id, "reason": reason},
                    created_at_utc=now,
                )
            conn.commit()

    def _release_budget(self, proposal_id: int, *, reason: str) -> None:
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            row = conn.execute(
                "SELECT actor_id, status, payload_json FROM divine_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            payload = json.loads(row["payload_json"])
            state = payload.get("promulgation") or {}
            if state.get("state") not in {"prepared", "uncertain"}:
                conn.commit()
                return
            conn.execute(
                """
                INSERT INTO divine_budget_ledger(
                    actor_id, budget_kind, delta, reason, performed_by,
                    intervention_id, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["actor_id"]),
                    BudgetKind.LEGISLATIVE.value,
                    LAW_BUDGET_COST,
                    f"Release of Law proposal {proposal_id}: {reason}",
                    "father",
                    state["intervention_id"],
                    now.isoformat(),
                ),
            )
            state["state"] = "released"
            state["released_at_utc"] = now.isoformat()
            state["release_reason"] = reason
            payload["promulgation"] = state
            conn.execute(
                """
                UPDATE divine_proposals
                SET payload_json = ?, status = ?
                WHERE id = ?
                """,
                (
                    json.dumps(payload, sort_keys=True),
                    LegislativeStatus.BLOCKED.value,
                    proposal_id,
                ),
            )
            self.governance.append_audit_in_transaction(
                conn,
                event_type="law_promulgation_released",
                actor_id="father",
                subject_actor_id=str(row["actor_id"]),
                payload={"proposal_id": proposal_id, "reason": reason},
                created_at_utc=now,
            )
            conn.commit()

    def _finalize(self, proposal_id: int, merge_commit_sha: str) -> PromulgationResult:
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            row = conn.execute(
                "SELECT actor_id, status, payload_json FROM divine_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            payload = json.loads(row["payload_json"])
            if str(row["status"]) == LegislativeStatus.PROMULGATED.value:
                existing = payload.get("merge_commit")
                if existing != merge_commit_sha:
                    raise RuntimeError("Promulgated Law has a different merge commit")
                conn.commit()
                return PromulgationResult(proposal_id, merge_commit_sha, True)
            if str(row["status"]) != LegislativeStatus.ACCEPTED.value:
                raise PromulgationBlocked("Only an accepted Law can be finalized")
            state = payload.get("promulgation") or {}
            if state.get("state") not in {"prepared", "uncertain"}:
                raise PromulgationBlocked("Law has no reserved promulgation attempt")
            state["state"] = "completed"
            state["completed_at_utc"] = now.isoformat()
            state["merge_commit"] = merge_commit_sha
            payload["promulgation"] = state
            payload["merge_commit"] = merge_commit_sha
            conn.execute(
                """
                UPDATE divine_proposals
                SET payload_json = ?, status = ?, decided_at_utc = ?, decided_by = ?
                WHERE id = ?
                """,
                (
                    json.dumps(payload, sort_keys=True),
                    LegislativeStatus.PROMULGATED.value,
                    now.isoformat(),
                    "father",
                    proposal_id,
                ),
            )
            self.governance.append_audit_in_transaction(
                conn,
                event_type="law_promulgated",
                actor_id="father",
                subject_actor_id=str(row["actor_id"]),
                payload={
                    "proposal_id": proposal_id,
                    "merge_commit": merge_commit_sha,
                    "intervention_id": state["intervention_id"],
                },
                created_at_utc=now,
            )
            conn.commit()
        return PromulgationResult(proposal_id, merge_commit_sha, False)

    def promulgate(self, proposal_id: int) -> PromulgationResult:
        stored = self.legislation.get(proposal_id)
        if stored["status"] == LegislativeStatus.PROMULGATED.value:
            merge_commit = stored["payload"].get("merge_commit")
            if not isinstance(merge_commit, str):
                raise RuntimeError("Promulgated Law is missing its merge commit")
            return PromulgationResult(proposal_id, merge_commit, True)

        authorization = self._authorization_from_dossier(stored)
        snapshot = self.git.pull_request(authorization.pr_number)
        state = self._promulgation_state(stored)

        if snapshot.merged:
            if state.get("state") not in {"prepared", "uncertain"}:
                raise PromulgationBlocked(
                    "Pull request was merged outside a prepared Creator promulgation"
                )
            if snapshot.head_sha != authorization.expected_head_sha:
                raise PromulgationBlocked("Merged pull request head does not match authorization")
            if not snapshot.merge_commit_sha:
                raise RuntimeError("Merged pull request is missing merge commit SHA")
            return self._finalize(proposal_id, snapshot.merge_commit_sha)

        blockers = self._preflight_blockers(
            stored,
            authorization,
            snapshot,
            require_budget=state.get("state") not in {"prepared", "uncertain"},
        )
        if blockers:
            if state.get("state") in {"prepared", "uncertain"}:
                self._release_budget(proposal_id, reason="; ".join(blockers))
            raise PromulgationBlocked("; ".join(blockers))

        self._reserve_budget(stored, authorization)

        # Re-read every mutable external and governance condition after reservation.
        stored = self.legislation.get(proposal_id)
        snapshot = self.git.pull_request(authorization.pr_number)
        blockers = self._preflight_blockers(
            stored,
            authorization,
            snapshot,
            require_budget=False,
        )
        if blockers:
            self._release_budget(proposal_id, reason="; ".join(blockers))
            raise PromulgationBlocked("; ".join(blockers))

        try:
            result = self.git.merge(authorization)
        except Exception as exc:
            self._set_uncertain(proposal_id, reason=f"merge outcome unknown: {type(exc).__name__}")
            raise

        if not result.merged or not result.merge_commit_sha:
            self._release_budget(
                proposal_id,
                reason=result.message or "Git provider did not merge the accepted Law",
            )
            raise PromulgationBlocked(result.message or "Git provider refused the merge")

        return self._finalize(proposal_id, result.merge_commit_sha)
