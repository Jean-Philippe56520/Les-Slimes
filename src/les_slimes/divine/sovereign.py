from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from .access import AUTHORIZED_REPOSITORY, DivineAccessPolicy


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


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
    source_main_sha: str
    main_is_current: bool
    drive_artifact_id: str
    manifest_digest: str
    patch_digest: str
    affected_files: tuple[str, ...]
    artifact_verified: bool
    patch_verified: bool
    governance_eligible: bool
    evidence_complete: bool
    experiment_required: bool = False
    experiment_passed: bool = False
    combined_experiment_required: bool = False
    combined_experiment_passed: bool = False


@dataclass(frozen=True, slots=True)
class ImplementationAuthorization:
    proposal_id: int
    candidate_actor_id: str
    source_main_sha: str
    drive_artifact_id: str
    manifest_digest: str
    patch_digest: str
    affected_files: tuple[str, ...]
    authorized_by: str = "father"


@dataclass(frozen=True, slots=True)
class CreatorImplementation:
    proposal_id: int
    candidate_actor_id: str
    branch: str
    pr_number: int
    head_sha: str
    base_sha: str
    implemented_files: tuple[str, ...]
    required_checks: tuple[str, ...]

    def validated(self) -> CreatorImplementation:
        if self.proposal_id < 1:
            raise ValueError("proposal_id must be positive")
        policy = DivineAccessPolicy(self.candidate_actor_id)
        if not self.branch.startswith("father/law-") or self.branch == "father/law-":
            raise PermissionError("Creator Law implementation must use a father/law-* branch")
        if any(char.isspace() for char in self.branch):
            raise PermissionError("Creator Law branch cannot contain whitespace")
        if self.pr_number < 1:
            raise ValueError("pr_number must be positive")
        if not _SHA_RE.fullmatch(self.head_sha):
            raise ValueError("head_sha must be a full lowercase Git SHA")
        if not _SHA_RE.fullmatch(self.base_sha):
            raise ValueError("base_sha must be a full lowercase Git SHA")
        if not self.implemented_files:
            raise ValueError("implemented_files must not be empty")
        if len(set(self.implemented_files)) != len(self.implemented_files):
            raise ValueError("implemented_files must not contain duplicates")
        for path in self.implemented_files:
            policy.assert_law_target_path(path)
        if not self.required_checks or any(not item.strip() for item in self.required_checks):
            raise ValueError("required_checks must contain non-empty checks")
        if len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("required_checks must not contain duplicates")
        return self


@dataclass(frozen=True, slots=True)
class MergeAuthorization:
    repository_full_name: str
    branch: str
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
    implementation_authorization: ImplementationAuthorization | None

    @property
    def implementation_authorized(self) -> bool:
        return self.implementation_authorization is not None


class SovereignCreatorCycle:
    """Mechanical gate between a divine Drive proposal and Creator implementation."""

    def blockers_for(self, candidate: LawCandidate) -> tuple[str, ...]:
        blockers: list[str] = []
        try:
            policy = DivineAccessPolicy(candidate.actor_id)
        except ValueError as exc:
            blockers.append(str(exc))
            policy = None

        if candidate.proposal_id < 1:
            blockers.append("proposal_id must be positive")
        if not _SHA_RE.fullmatch(candidate.source_main_sha):
            blockers.append("source_main_sha must be a full lowercase Git SHA")
        if not candidate.main_is_current:
            blockers.append("proposal is not based on the current main")
        if not candidate.drive_artifact_id.strip():
            blockers.append("drive_artifact_id is required")
        if not _DIGEST_RE.fullmatch(candidate.manifest_digest):
            blockers.append("manifest_digest must be a lowercase SHA-256 digest")
        if not _DIGEST_RE.fullmatch(candidate.patch_digest):
            blockers.append("patch_digest must be a lowercase SHA-256 digest")
        if not candidate.affected_files:
            blockers.append("affected_files must not be empty")
        elif len(set(candidate.affected_files)) != len(candidate.affected_files):
            blockers.append("affected_files must not contain duplicates")
        elif policy is not None:
            for path in candidate.affected_files:
                try:
                    policy.assert_law_target_path(path)
                except PermissionError as exc:
                    blockers.append(f"invalid Law target {path}: {exc}")
        if not candidate.artifact_verified:
            blockers.append("Drive proposal artifact has not been verified")
        if not candidate.patch_verified:
            blockers.append("proposal patch digest has not been verified")
        if not candidate.governance_eligible:
            blockers.append("candidate is not eligible under current governance")
        if not candidate.evidence_complete:
            blockers.append("scientific or technical evidence is incomplete")
        if candidate.experiment_required and not candidate.experiment_passed:
            blockers.append("required isolated experiment has not passed")
        if candidate.combined_experiment_required and not candidate.combined_experiment_passed:
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
        authorization: ImplementationAuthorization | None = None
        if decision == CreatorDecision.ACCEPT and not blockers:
            authorization = ImplementationAuthorization(
                proposal_id=candidate.proposal_id,
                candidate_actor_id=candidate.actor_id,
                source_main_sha=candidate.source_main_sha,
                drive_artifact_id=candidate.drive_artifact_id,
                manifest_digest=candidate.manifest_digest,
                patch_digest=candidate.patch_digest,
                affected_files=candidate.affected_files,
            )
        return CreatorReview(
            decision=decision,
            reason=normalized_reason,
            blockers=blockers,
            implementation_authorization=authorization,
        )


def merge_authorization_from_implementation(
    implementation: CreatorImplementation,
) -> MergeAuthorization:
    implementation.validated()
    return MergeAuthorization(
        repository_full_name=AUTHORIZED_REPOSITORY,
        branch=implementation.branch,
        pr_number=implementation.pr_number,
        expected_head_sha=implementation.head_sha,
        expected_base_sha=implementation.base_sha,
        candidate_actor_id=implementation.candidate_actor_id,
        proposal_id=implementation.proposal_id,
    )
