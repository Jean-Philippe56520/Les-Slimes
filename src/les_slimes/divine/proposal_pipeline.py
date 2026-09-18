from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from ..database.base import RelationalRepository
from .access import DivineAccessPolicy
from .actor_gateway import DivineRequestMetadata
from .archive_gateway import ArchiveItem, ArchiveProvider, DivineArchiveGateway
from .git_gateway import DivineGitGateway, ReadOnlyGitProvider
from .legislation import DivineLegislationService, LawDossier, ProposalProvenance
from .session_identity import DivineSessionBindingService


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LawProposalDraft:
    title: str
    observation: str
    hypothesis: str
    expected_benefit: str
    risk: str
    affected_files: tuple[str, ...]
    patch_text: str
    tests_text: str = ""
    results_text: str = ""
    evidence: tuple[str, ...] = ()
    experiment_refs: tuple[str, ...] = ()

    def validated_for(self, actor_id: str) -> "LawProposalDraft":
        required = {
            "title": self.title,
            "observation": self.observation,
            "hypothesis": self.hypothesis,
            "expected_benefit": self.expected_benefit,
            "risk": self.risk,
            "patch_text": self.patch_text,
        }
        for name, value in required.items():
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not self.affected_files:
            raise ValueError("affected_files must not be empty")
        if len(set(self.affected_files)) != len(self.affected_files):
            raise ValueError("affected_files must not contain duplicates")
        policy = DivineAccessPolicy(actor_id)
        for path in self.affected_files:
            policy.assert_law_target_path(path)
        return self


@dataclass(frozen=True, slots=True)
class LawProposalSubmission:
    proposal_id: int
    actor_id: str
    source_main_sha: str
    manifest_item_id: str
    manifest_digest: str
    patch_digest: str
    artifact_ids: tuple[str, ...]


class DivineLawProposalPipeline:
    """Build immutable Drive artifacts then persist the authoritative Law dossier.

    Drive is intentionally non-transactional. If persistence fails after artifact
    creation, the orphaned artifacts are harmless because no canonical proposal points
    to them.
    """

    def __init__(
        self,
        repository: RelationalRepository,
        *,
        git_provider: ReadOnlyGitProvider,
        archive_provider: ArchiveProvider,
    ) -> None:
        self.repository = repository
        self.sessions = DivineSessionBindingService(repository)
        self.legislation = DivineLegislationService(repository)
        self.git_provider = git_provider
        self.archive_provider = archive_provider

    def _binding(self, meta: Mapping[str, Any]):
        request_meta = DivineRequestMetadata.from_meta(meta)
        binding = self.sessions.resolve(
            session_id=request_meta.session_id,
            subject_id=request_meta.subject_id,
        )
        if binding.actor_id not in {"order", "chaos"}:
            raise PermissionError("LAW_PROPOSAL_REQUIRES_ORDER_OR_CHAOS")
        return binding

    def submit(
        self,
        meta: Mapping[str, Any],
        *,
        draft: LawProposalDraft,
    ) -> LawProposalSubmission:
        binding = self._binding(meta)
        actor_id = binding.actor_id
        draft.validated_for(actor_id)

        source_main_sha = DivineGitGateway(actor_id, self.git_provider).main_sha()
        if len(source_main_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_main_sha):
            raise ValueError("Git provider returned an invalid main SHA")

        patch_digest = _sha256_text(draft.patch_text)
        proposal_text = (
            f"# {draft.title.strip()}\n\n"
            f"## Observation\n{draft.observation.strip()}\n\n"
            f"## Hypothèse\n{draft.hypothesis.strip()}\n\n"
            f"## Bénéfice attendu\n{draft.expected_benefit.strip()}\n\n"
            f"## Risque\n{draft.risk.strip()}\n"
        )
        proposal_digest = _sha256_text(proposal_text)
        tests_digest = _sha256_text(draft.tests_text)
        results_digest = _sha256_text(draft.results_text)

        archive = DivineArchiveGateway(actor_id, self.archive_provider)
        prefix = f"{actor_id}-{patch_digest[:12]}"
        proposal_item = archive.create_proposal_text(
            name=f"{prefix}-proposal.md",
            content=proposal_text,
        )
        patch_item = archive.create_proposal_text(
            name=f"{prefix}-patch.diff",
            content=draft.patch_text,
        )
        tests_item = archive.create_proposal_text(
            name=f"{prefix}-tests.diff",
            content=draft.tests_text,
        )
        results_item = archive.create_proposal_text(
            name=f"{prefix}-results.txt",
            content=draft.results_text,
        )

        manifest_payload = {
            "actor_id": actor_id,
            "source_main_sha": source_main_sha,
            "affected_files": list(draft.affected_files),
            "artifacts": {
                "proposal": {
                    "id": proposal_item.id,
                    "sha256": proposal_digest,
                },
                "patch": {
                    "id": patch_item.id,
                    "sha256": patch_digest,
                },
                "tests": {
                    "id": tests_item.id,
                    "sha256": tests_digest,
                },
                "results": {
                    "id": results_item.id,
                    "sha256": results_digest,
                },
            },
            "evidence": list(draft.evidence),
            "experiment_refs": list(draft.experiment_refs),
        }
        manifest_text = json.dumps(
            manifest_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        manifest_digest = _sha256_text(manifest_text)
        manifest_item = archive.create_proposal_text(
            name=f"{prefix}-manifest.json",
            content=manifest_text,
        )

        # Re-resolve immediately before the canonical DB write so revocation or actor
        # deactivation during external Drive writes fails closed.
        binding = self._binding(meta)
        if binding.actor_id != actor_id:
            raise PermissionError("DIVINE_SESSION_IDENTITY_CHANGED")

        dossier = LawDossier(
            title=draft.title,
            observation=draft.observation,
            hypothesis=draft.hypothesis,
            expected_benefit=draft.expected_benefit,
            risk=draft.risk,
            source_main_sha=source_main_sha,
            drive_artifact_id=manifest_item.id,
            manifest_digest=manifest_digest,
            patch_digest=patch_digest,
            affected_files=draft.affected_files,
            evidence=draft.evidence,
            experiment_refs=draft.experiment_refs,
        )
        proposal_id = self.legislation.submit(
            actor_id,
            dossier,
            provenance=ProposalProvenance(
                session_hash=binding.session_hash,
                subject_hash=binding.subject_hash,
            ),
        )
        return LawProposalSubmission(
            proposal_id=proposal_id,
            actor_id=actor_id,
            source_main_sha=source_main_sha,
            manifest_item_id=manifest_item.id,
            manifest_digest=manifest_digest,
            patch_digest=patch_digest,
            artifact_ids=(
                proposal_item.id,
                patch_item.id,
                tests_item.id,
                results_item.id,
                manifest_item.id,
            ),
        )
