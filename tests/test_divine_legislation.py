import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.divine import (
    CreatorDecision,
    CreatorImplementation,
    DivineLegislationService,
    LawCandidate,
    LawDossier,
    LegislativeStatus,
)
from les_slimes.governance.models import BudgetKind, PowerLevel, SanctionType
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.governance.storage import GovernanceStorage
from les_slimes.world.engine import World


SOURCE = "a" * 40
MANIFEST = "b" * 64
PATCH = "c" * 64


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=919,
                width=20.0,
                height=15.0,
                initial_slimes=4,
                initial_food=5,
                max_food=20,
                food_spawn_probability=0.0,
            )
        )
    )
    return repo


def grant_law(repo, actor_id="chaos"):
    admin = GovernanceAdminService(repo)
    admin.set_power_level(actor_id, PowerLevel.LAW, reason="law test")
    admin.adjust_budget(actor_id, BudgetKind.LEGISLATIVE, 2, reason="law test allocation")
    return admin


def dossier(**overrides):
    data = {
        "title": "Adaptive niche law",
        "observation": "Several strategies are converging.",
        "hypothesis": "A bounded variation mechanism may preserve alternatives.",
        "expected_benefit": "Maintain several viable strategies.",
        "risk": "Variation may add noise or reduce fragile lineages.",
        "source_main_sha": SOURCE,
        "drive_artifact_id": "drive-law-52",
        "manifest_digest": MANIFEST,
        "patch_digest": PATCH,
        "affected_files": (
            "src/les_slimes/world/engine.py",
            "tests/test_engine.py",
        ),
        "evidence": ("EXP-1", "EXP-2"),
        "experiment_refs": ("EXP-1", "EXP-2"),
    }
    data.update(overrides)
    return LawDossier(**data)


def candidate(proposal_id, source=None, **overrides):
    source = source or dossier()
    data = {
        "actor_id": "chaos",
        "proposal_id": proposal_id,
        "source_main_sha": source.source_main_sha,
        "main_is_current": True,
        "drive_artifact_id": source.drive_artifact_id,
        "manifest_digest": source.manifest_digest,
        "patch_digest": source.patch_digest,
        "affected_files": source.affected_files,
        "artifact_verified": True,
        "patch_verified": True,
        "governance_eligible": False,
        "evidence_complete": True,
    }
    data.update(overrides)
    return LawCandidate(**data)


def implementation(proposal_id, **overrides):
    data = {
        "proposal_id": proposal_id,
        "candidate_actor_id": "chaos",
        "branch": f"father/law-{proposal_id}-adaptive-niches",
        "pr_number": 52,
        "head_sha": "d" * 40,
        "base_sha": SOURCE,
        "implemented_files": (
            "src/les_slimes/world/engine.py",
            "tests/test_engine.py",
        ),
        "required_checks": ("python", "postgres", "docker"),
    }
    data.update(overrides)
    return CreatorImplementation(**data)


def test_god_submits_drive_backed_law_without_git_coordinates(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    stored = service.get(proposal_id)
    assert stored["actor_id"] == "chaos"
    assert stored["status"] == LegislativeStatus.PROPOSED.value
    assert stored["payload"]["drive_artifact_id"] == "drive-law-52"
    assert "branch" not in stored["payload"]
    assert "pr_number" not in stored["payload"]
    assert GovernanceStorage(repo).validate_audit_chain()


def test_non_divine_actor_and_protected_target_cannot_submit(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)
    with pytest.raises(ValueError):
        service.submit("observer", dossier())
    with pytest.raises(PermissionError):
        service.submit("chaos", dossier(affected_files=("README.md",)))


def test_creator_review_recomputes_real_governance(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    blocked = service.review(
        proposal_id,
        candidate(proposal_id, governance_eligible=True),
        decision=CreatorDecision.ACCEPT,
        reason="Candidate appears sound.",
    )
    assert not blocked.implementation_authorized
    assert service.get(proposal_id)["status"] == LegislativeStatus.BLOCKED.value

    grant_law(repo)
    accepted = service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="Authority and evidence are complete.",
    )
    assert accepted.implementation_authorized
    assert service.get(proposal_id)["status"] == LegislativeStatus.ACCEPTED.value


def test_legislative_freeze_blocks_acceptance(tmp_path):
    repo = build_repo(tmp_path)
    admin = grant_law(repo)
    admin.impose_sanction(
        "chaos", SanctionType.FREEZE_LEGISLATIVE_BUDGET, reason="temporary freeze"
    )
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    review = service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="Review during freeze.",
    )
    assert not review.implementation_authorized
    assert service.get(proposal_id)["status"] == LegislativeStatus.BLOCKED.value


def test_review_is_bound_to_drive_artifact_and_patch_digest(tmp_path):
    repo = build_repo(tmp_path)
    grant_law(repo)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    review = service.review(
        proposal_id,
        candidate(
            proposal_id,
            patch_digest="f" * 64,
            drive_artifact_id="another-drive-item",
        ),
        decision=CreatorDecision.ACCEPT,
        reason="Attempted review of another artifact.",
    )
    assert not review.implementation_authorized
    assert any("patch_digest" in blocker for blocker in review.blockers)
    assert any("drive_artifact_id" in blocker for blocker in review.blockers)


def test_only_father_can_review_attach_or_promulgate(tmp_path):
    repo = build_repo(tmp_path)
    grant_law(repo)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    with pytest.raises(PermissionError, match="Father"):
        service.review(
            proposal_id,
            candidate(proposal_id),
            decision=CreatorDecision.ACCEPT,
            reason="self approval",
            performed_by="chaos",
        )

    service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="accepted",
    )
    with pytest.raises(PermissionError, match="Father"):
        service.attach_creator_implementation(
            proposal_id, implementation(proposal_id), performed_by="chaos"
        )


def test_creator_implementation_must_match_reviewed_file_scope_and_source(tmp_path):
    repo = build_repo(tmp_path)
    grant_law(repo)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="accepted",
    )
    with pytest.raises(ValueError, match="file scope"):
        service.attach_creator_implementation(
            proposal_id,
            implementation(proposal_id, implemented_files=("src/les_slimes/world/engine.py",)),
        )
    with pytest.raises(ValueError, match="reviewed main SHA"):
        service.attach_creator_implementation(
            proposal_id,
            implementation(proposal_id, base_sha="e" * 40),
        )

    service.attach_creator_implementation(proposal_id, implementation(proposal_id))
    stored = service.get(proposal_id)
    assert stored["payload"]["creator_implementation"]["branch"].startswith("father/law-")


def test_god_can_amend_blocked_drive_proposal_but_not_accepted_law(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="Insufficient authority.",
    )
    amended = dossier(patch_digest="e" * 64, drive_artifact_id="drive-law-52-v2")
    service.amend("chaos", proposal_id, amended)
    assert service.get(proposal_id)["payload"]["patch_digest"] == "e" * 64

    grant_law(repo)
    service.review(
        proposal_id,
        candidate(proposal_id, amended),
        decision=CreatorDecision.ACCEPT,
        reason="Amended law accepted.",
    )
    with pytest.raises(PermissionError):
        service.amend("chaos", proposal_id, dossier(patch_digest="f" * 64))
