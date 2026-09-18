from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ..database.base import RelationalRepository
from ..governance.invariants import ensure_governance_invariants
from ..governance.models import BudgetKind, PowerLevel, SanctionType
from ..governance.storage import GovernanceStorage
from ..runtime.storage import RuntimeStorage
from .access import DivineAccessPolicy
from .sovereign import (
    CreatorDecision,
    CreatorImplementation,
    CreatorReview,
    LawCandidate,
    SovereignCreatorCycle,
)


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
LAW_BUDGET_COST = 1


class LegislativeStatus(StrEnum):
    PROPOSED = "proposed"
    NEEDS_EVIDENCE = "needs_evidence"
    NEEDS_AMENDMENT = "needs_amendment"
    WAITING = "waiting"
    BLOCKED = "blocked"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PROMULGATED = "promulgated"
    SUPERSEDED = "superseded"


_EDITABLE_STATUSES = frozenset(
    {
        LegislativeStatus.PROPOSED,
        LegislativeStatus.NEEDS_EVIDENCE,
        LegislativeStatus.NEEDS_AMENDMENT,
        LegislativeStatus.WAITING,
        LegislativeStatus.BLOCKED,
    }
)
_TERMINAL_STATUSES = frozenset(
    {
        LegislativeStatus.REJECTED,
        LegislativeStatus.PROMULGATED,
        LegislativeStatus.SUPERSEDED,
    }
)


@dataclass(frozen=True, slots=True)
class LawDossier:
    title: str
    observation: str
    hypothesis: str
    expected_benefit: str
    risk: str
    source_main_sha: str
    drive_artifact_id: str
    manifest_digest: str
    patch_digest: str
    affected_files: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    experiment_refs: tuple[str, ...] = ()

    def validated_for(self, actor_id: str) -> LawDossier:
        policy = DivineAccessPolicy(actor_id)
        required_text = {
            "title": self.title,
            "observation": self.observation,
            "hypothesis": self.hypothesis,
            "expected_benefit": self.expected_benefit,
            "risk": self.risk,
            "drive_artifact_id": self.drive_artifact_id,
        }
        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not _SHA_RE.fullmatch(self.source_main_sha):
            raise ValueError("source_main_sha must be a full lowercase Git SHA")
        if not _DIGEST_RE.fullmatch(self.manifest_digest):
            raise ValueError("manifest_digest must be a lowercase SHA-256 digest")
        if not _DIGEST_RE.fullmatch(self.patch_digest):
            raise ValueError("patch_digest must be a lowercase SHA-256 digest")
        if not self.affected_files:
            raise ValueError("affected_files must not be empty")
        if len(set(self.affected_files)) != len(self.affected_files):
            raise ValueError("affected_files must not contain duplicates")
        for path in self.affected_files:
            policy.assert_law_target_path(path)
        return self

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_files"] = list(self.affected_files)
        payload["evidence"] = list(self.evidence)
        payload["experiment_refs"] = list(self.experiment_refs)
        return payload


class DivineLegislationService:
    """Persistent Drive-backed divine proposal and Father-only review path."""

    def __init__(self, repository: RelationalRepository) -> None:
        ensure_governance_invariants(repository)
        self.repository = repository
        self.runtime = RuntimeStorage(repository)
        self.storage = GovernanceStorage(repository)  # type: ignore[arg-type]
        self.creator_cycle = SovereignCreatorCycle()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _require_father(performed_by: str) -> None:
        if performed_by != "father":
            raise PermissionError("Only the Father may decide, implement or promulgate a Law")

    def _active_divine_actor(self, actor_id: str) -> None:
        DivineAccessPolicy(actor_id)
        actor = self.runtime.get_actor(actor_id)
        if not actor.active:
            raise PermissionError("Inactive gods cannot submit or amend Laws")

    def _law_governance_eligible(self, actor_id: str) -> bool:
        actor = self.runtime.get_actor(actor_id)
        if not actor.active:
            return False
        state = self.storage.get_actor_state(actor_id)
        sanctions = self.storage.active_sanctions(actor_id, now_utc=self._now())
        sanction_types = {sanction.sanction_type for sanction in sanctions}
        if SanctionType.SUSPEND in sanction_types:
            return False
        if SanctionType.FREEZE_LEGISLATIVE_BUDGET in sanction_types:
            return False
        effective_power = state.max_power_level
        for sanction in sanctions:
            if sanction.sanction_type == SanctionType.MAX_POWER_LEVEL:
                effective_power = min(
                    effective_power,
                    PowerLevel(int(sanction.parameters["power_level"])),
                )
        if effective_power < PowerLevel.LAW:
            return False
        return self.storage.budget_balance(actor_id, BudgetKind.LEGISLATIVE) >= LAW_BUDGET_COST

    def submit(self, actor_id: str, dossier: LawDossier) -> int:
        self._active_divine_actor(actor_id)
        dossier.validated_for(actor_id)
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            cursor = conn.execute(
                """
                INSERT INTO divine_proposals(
                    actor_id, proposal_type, title, payload_json, status, created_at_utc
                ) VALUES (?, 'law', ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    dossier.title,
                    json.dumps(dossier.to_payload(), sort_keys=True),
                    LegislativeStatus.PROPOSED.value,
                    now.isoformat(),
                ),
            )
            proposal_id = int(cursor.lastrowid)
            self.storage.append_audit_in_transaction(
                conn,
                event_type="law_drive_dossier_submitted",
                actor_id=actor_id,
                subject_actor_id=actor_id,
                payload={
                    "proposal_id": proposal_id,
                    "source_main_sha": dossier.source_main_sha,
                    "drive_artifact_id": dossier.drive_artifact_id,
                    "manifest_digest": dossier.manifest_digest,
                    "patch_digest": dossier.patch_digest,
                    "affected_files": list(dossier.affected_files),
                },
                created_at_utc=now,
            )
            conn.commit()
        return proposal_id

    def get(self, proposal_id: int) -> dict[str, Any]:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        if row is None or str(row["proposal_type"]) != "law":
            raise KeyError(proposal_id)
        return {
            "id": int(row["id"]),
            "actor_id": str(row["actor_id"]),
            "title": str(row["title"]),
            "payload": json.loads(row["payload_json"]),
            "status": str(row["status"]),
            "created_at_utc": str(row["created_at_utc"]),
            "decided_at_utc": str(row["decided_at_utc"]) if row["decided_at_utc"] else None,
            "decided_by": str(row["decided_by"]) if row["decided_by"] else None,
            "decision_reason": str(row["decision_reason"]) if row["decision_reason"] else None,
        }

    def amend(self, actor_id: str, proposal_id: int, dossier: LawDossier) -> None:
        self._active_divine_actor(actor_id)
        dossier.validated_for(actor_id)
        existing = self.get(proposal_id)
        if existing["actor_id"] != actor_id:
            raise PermissionError("A god may amend only its own Law")
        if LegislativeStatus(existing["status"]) not in _EDITABLE_STATUSES:
            raise PermissionError("This Law is no longer editable by its proposing god")
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            conn.execute(
                """
                UPDATE divine_proposals
                SET title = ?, payload_json = ?, status = ?,
                    decided_at_utc = NULL, decided_by = NULL, decision_reason = NULL
                WHERE id = ?
                """,
                (
                    dossier.title,
                    json.dumps(dossier.to_payload(), sort_keys=True),
                    LegislativeStatus.PROPOSED.value,
                    proposal_id,
                ),
            )
            self.storage.append_audit_in_transaction(
                conn,
                event_type="law_drive_dossier_amended",
                actor_id=actor_id,
                subject_actor_id=actor_id,
                payload={
                    "proposal_id": proposal_id,
                    "source_main_sha": dossier.source_main_sha,
                    "drive_artifact_id": dossier.drive_artifact_id,
                    "patch_digest": dossier.patch_digest,
                },
                created_at_utc=now,
            )
            conn.commit()

    @staticmethod
    def _review_status(review: CreatorReview) -> LegislativeStatus:
        if review.decision == CreatorDecision.ACCEPT:
            return (
                LegislativeStatus.ACCEPTED
                if review.implementation_authorized
                else LegislativeStatus.BLOCKED
            )
        if review.decision == CreatorDecision.REJECT:
            return LegislativeStatus.REJECTED
        if review.decision == CreatorDecision.REQUEST_AMENDMENT:
            return LegislativeStatus.NEEDS_AMENDMENT
        if review.decision == CreatorDecision.REQUEST_EXPERIMENT:
            return LegislativeStatus.NEEDS_EVIDENCE
        return LegislativeStatus.WAITING

    @staticmethod
    def _dossier_mismatches(stored: dict[str, Any], candidate: LawCandidate) -> tuple[str, ...]:
        expected = stored["payload"]
        pairs = {
            "actor_id": (stored["actor_id"], candidate.actor_id),
            "proposal_id": (stored["id"], candidate.proposal_id),
            "source_main_sha": (expected.get("source_main_sha"), candidate.source_main_sha),
            "drive_artifact_id": (expected.get("drive_artifact_id"), candidate.drive_artifact_id),
            "manifest_digest": (expected.get("manifest_digest"), candidate.manifest_digest),
            "patch_digest": (expected.get("patch_digest"), candidate.patch_digest),
            "affected_files": (
                tuple(expected.get("affected_files", [])),
                tuple(candidate.affected_files),
            ),
        }
        mismatches = [
            f"candidate {name} does not match persisted dossier"
            for name, (dossier_value, candidate_value) in pairs.items()
            if dossier_value != candidate_value
        ]
        return tuple(mismatches)

    def review(
        self,
        proposal_id: int,
        candidate: LawCandidate,
        *,
        decision: CreatorDecision,
        reason: str,
        performed_by: str = "father",
    ) -> CreatorReview:
        self._require_father(performed_by)
        stored = self.get(proposal_id)
        if LegislativeStatus(stored["status"]) in _TERMINAL_STATUSES:
            raise PermissionError("Terminal Laws cannot be reviewed again")
        candidate = replace(
            candidate,
            governance_eligible=self._law_governance_eligible(stored["actor_id"]),
        )
        review = self.creator_cycle.review(candidate, decision=decision, reason=reason)
        mismatches = self._dossier_mismatches(stored, candidate)
        if mismatches:
            review = CreatorReview(
                decision=review.decision,
                reason=review.reason,
                blockers=(*mismatches, *review.blockers),
                implementation_authorization=None,
            )
        status = self._review_status(review)
        now = self._now()
        payload = dict(stored["payload"])
        payload["last_review"] = {
            "decision": review.decision.value,
            "blockers": list(review.blockers),
            "reviewed_source_main_sha": candidate.source_main_sha,
            "reviewed_drive_artifact_id": candidate.drive_artifact_id,
            "reviewed_manifest_digest": candidate.manifest_digest,
            "reviewed_patch_digest": candidate.patch_digest,
        }
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            conn.execute(
                """
                UPDATE divine_proposals
                SET payload_json = ?, status = ?, decided_at_utc = ?,
                    decided_by = ?, decision_reason = ?
                WHERE id = ?
                """,
                (
                    json.dumps(payload, sort_keys=True),
                    status.value,
                    now.isoformat(),
                    performed_by,
                    review.reason,
                    proposal_id,
                ),
            )
            self.storage.append_audit_in_transaction(
                conn,
                event_type="law_reviewed",
                actor_id=performed_by,
                subject_actor_id=stored["actor_id"],
                payload={
                    "proposal_id": proposal_id,
                    "decision": review.decision.value,
                    "status": status.value,
                    "blockers": list(review.blockers),
                    "source_main_sha": candidate.source_main_sha,
                    "drive_artifact_id": candidate.drive_artifact_id,
                },
                created_at_utc=now,
            )
            conn.commit()
        return review

    def attach_creator_implementation(
        self,
        proposal_id: int,
        implementation: CreatorImplementation,
        *,
        performed_by: str = "father",
    ) -> None:
        self._require_father(performed_by)
        implementation.validated()
        stored = self.get(proposal_id)
        if stored["status"] != LegislativeStatus.ACCEPTED.value:
            raise PermissionError("Only an accepted Law can receive a Creator implementation")
        if implementation.proposal_id != proposal_id:
            raise ValueError("implementation proposal_id does not match")
        if implementation.candidate_actor_id != stored["actor_id"]:
            raise ValueError("implementation actor does not match the proposing god")
        payload = dict(stored["payload"])
        if implementation.base_sha != payload.get("source_main_sha"):
            raise ValueError("Creator implementation must still be based on the reviewed main SHA")
        proposed_files = set(payload.get("affected_files", []))
        implemented_files = set(implementation.implemented_files)
        if implemented_files != proposed_files:
            raise ValueError("Creator implementation file scope must match the reviewed proposal")
        impl_payload = asdict(implementation)
        impl_payload["implemented_files"] = list(implementation.implemented_files)
        impl_payload["required_checks"] = list(implementation.required_checks)
        payload["creator_implementation"] = impl_payload
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            conn.execute(
                "UPDATE divine_proposals SET payload_json = ? WHERE id = ?",
                (json.dumps(payload, sort_keys=True), proposal_id),
            )
            self.storage.append_audit_in_transaction(
                conn,
                event_type="law_creator_implementation_attached",
                actor_id=performed_by,
                subject_actor_id=stored["actor_id"],
                payload={
                    "proposal_id": proposal_id,
                    "branch": implementation.branch,
                    "pr_number": implementation.pr_number,
                    "head_sha": implementation.head_sha,
                    "base_sha": implementation.base_sha,
                    "implemented_files": list(implementation.implemented_files),
                    "required_checks": list(implementation.required_checks),
                },
                created_at_utc=now,
            )
            conn.commit()

    def mark_promulgated(
        self,
        proposal_id: int,
        *,
        merge_commit: str,
        performed_by: str = "father",
    ) -> None:
        self._require_father(performed_by)
        if not _SHA_RE.fullmatch(merge_commit):
            raise ValueError("merge_commit must be a full lowercase Git SHA")
        stored = self.get(proposal_id)
        if stored["status"] != LegislativeStatus.ACCEPTED.value:
            raise PermissionError("Only an accepted Law can be marked promulgated")
        payload = dict(stored["payload"])
        payload["merge_commit"] = merge_commit
        now = self._now()
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
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
                    performed_by,
                    proposal_id,
                ),
            )
            self.storage.append_audit_in_transaction(
                conn,
                event_type="law_promulgated",
                actor_id=performed_by,
                subject_actor_id=stored["actor_id"],
                payload={"proposal_id": proposal_id, "merge_commit": merge_commit},
                created_at_utc=now,
            )
            conn.commit()
