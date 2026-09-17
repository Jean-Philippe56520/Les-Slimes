from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .access import AUTHORIZED_REPOSITORY, DivineAccessPolicy


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class CreatorDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    WAIT = "wait"
    REQUEST_AMENDMENT = "request_amendment"
    REQUEST_EXPERIMENT = "request_experiment"


@dataclass(frozen=True, slots=True)
class LawCandidate:
    actor_id: str
    proposal_id: int
    branch: str
    pr_number: int
    head_sha: str
    base_sha: str
    base_is_current: bool
    pr_is_open: bool
    pr_is_mergeable: bool
    required_checks: tuple[str, ...]
    passed_checks: frozenset[str]
    governance_eligible: bool
    evidence_complete: bool
    experiment_required: bool = False
    experiment_passed: bool = False
    combined_experiment_required: bool = False
    combined_experiment_passed: bool = False


@dataclass(frozen=True, slots=True)
class MergeAuthorization:
    repository_full_name: str
    pr_number: int
    expected_head_sha: str
    expected_base_sha: str
    candidate_actor_id: str
    proposal_id: int
    authorized_by: str = "father"


@dataclass(frozen=True, slots=True)
class CreatorReview:
    decision: CreatorDecision
    reason: str
    blockers: tuple[str, ...]
    merge_authorization: MergeAuthorization | None

    @property
    def promulgation_authorized(self) -> bool:
        return self.merge_authorization is not None


class SovereignCreatorCycle:
    """Mechanical gate between a divine law candidate and a merge on main.

    The Creator may choose any political decision, including doing nothing. A decision to
    accept authorizes promulgation only when every structural gate is satisfied. The
    returned MergeAuthorization binds the exact PR head and reviewed main base SHA.
    """

    def blockers_for(self, candidate: LawCandidate) -> tuple[str, ...]:
        blockers: list[str] = []

        try:
            policy = DivineAccessPolicy(candidate.actor_id)
            policy.assert_git_write_branch(candidate.branch)
        except (ValueError, PermissionError) as exc:
            blockers.append(str(exc))

        if candidate.proposal_id < 1:
            blockers.append("proposal_id must be positive")
        if candidate.pr_number < 1:
            blockers.append("pr_number must be positive")
        if not _SHA_RE.fullmatch(candidate.head_sha):
            blockers.append("head_sha must be a full lowercase Git SHA")
        if not _SHA_RE.fullmatch(candidate.base_sha):
            blockers.append("base_sha must be a full lowercase Git SHA")
        if not candidate.base_is_current:
            blockers.append("candidate is not based on the current main")
        if not candidate.pr_is_open:
            blockers.append("pull request is not open")
        if not candidate.pr_is_mergeable:
            blockers.append("pull request is not mergeable")
        if not candidate.required_checks:
            blockers.append("no required checks were declared")
        else:
            missing = sorted(set(candidate.required_checks) - set(candidate.passed_checks))
            if missing:
                blockers.append("required checks not passed: " + ", ".join(missing))
        if not candidate.governance_eligible:
            blockers.append("candidate is not eligible under current governance")
        if not candidate.evidence_complete:
            blockers.append("scientific or technical evidence is incomplete")
        if candidate.experiment_required and not candidate.experiment_passed:
            blockers.append("required isolated experiment has not passed")
        if (
            candidate.combined_experiment_required
            and not candidate.combined_experiment_passed
        ):
            blockers.append("required combined experiment has not passed")

        return tuple(blockers)

    def review(
        self,
        candidate: LawCandidate,
        *,
        decision: CreatorDecision,
        reason: str,
    ) -> CreatorReview:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("Creator review requires a non-empty reason")

        blockers = self.blockers_for(candidate)
        authorization: MergeAuthorization | None = None
        if decision == CreatorDecision.ACCEPT and not blockers:
            authorization = MergeAuthorization(
                repository_full_name=AUTHORIZED_REPOSITORY,
                pr_number=candidate.pr_number,
                expected_head_sha=candidate.head_sha,
                expected_base_sha=candidate.base_sha,
                candidate_actor_id=candidate.actor_id,
                proposal_id=candidate.proposal_id,
            )

        return CreatorReview(
            decision=decision,
            reason=normalized_reason,
            blockers=blockers,
            merge_authorization=authorization,
        )
