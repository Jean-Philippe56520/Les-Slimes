import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.divine import (
    CreatorDecision,
    DivineLegislationService,
    LawCandidate,
    LawDossier,
    LegislativeStatus,
)
from les_slimes.governance.models import BudgetKind, PowerLevel, SanctionType
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.governance.storage import GovernanceStorage
from les_slimes.world.engine import World


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
    admin.adjust_budget(
        actor_id,
        BudgetKind.LEGISLATIVE,
        2,
        reason="law test allocation",
    )
    return admin


def dossier(actor_id="chaos", **overrides):
    data = {
        "title": "Adaptive niche law",
        "observation": "Several strategies are converging.",
        "hypothesis": "A bounded variation mechanism may preserve alternatives.",
        "expected_benefit": "Maintain several viable strategies.",
        "risk": "Variation may add noise or reduce fragile lineages.",
        "branch": f"god/{actor_id}/adaptive-niches",
        "pr_number": 52,
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "required_checks": ("python", "postgres", "docker"),
        "evidence": ("EXP-1", "EXP-2"),
        "experiment_refs": ("EXP-1", "EXP-2"),
    }
    data.update(overrides)
    return LawDossier(**data)


def candidate(proposal_id, source_dossier=None, **overrides):
    source = source_dossier or dossier()
    data = {
        "actor_id": "chaos",
        "proposal_id": proposal_id,
        "branch": source.branch,
        "pr_number": source.pr_number,
        "head_sha": source.head_sha,
        "base_sha": source.base_sha,
        "base_is_current": True,
        "pr_is_open": True,
        "pr_is_mergeable": True,
        "required_checks": source.required_checks,
        "passed_checks": frozenset(source.required_checks),
        # The service must ignore this caller assertion and recompute governance.
        "governance_eligible": False,
        "evidence_complete": True,
    }
    data.update(overrides)
    return LawCandidate(**data)


def test_god_can_submit_law_without_execution_budget_or_power(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)

    proposal_id = service.submit("chaos", dossier())
    stored = service.get(proposal_id)

    assert stored["actor_id"] == "chaos"
    assert stored["status"] == LegislativeStatus.PROPOSED.value
    assert stored["payload"]["branch"] == "god/chaos/adaptive-niches"
    assert GovernanceStorage(repo).validate_audit_chain()


def test_non_divine_actor_and_foreign_branch_cannot_submit_law(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)

    with pytest.raises(ValueError):
        service.submit("observer", dossier())
    with pytest.raises(PermissionError):
        service.submit("chaos", dossier(branch="god/order/foreign"))


def test_creator_review_recomputes_real_governance(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())

    blocked = service.review(
        proposal_id,
        candidate(proposal_id, governance_eligible=True),
        decision=CreatorDecision.ACCEPT,
        reason="Candidate appears technically sound.",
    )
    assert not blocked.promulgation_authorized
    assert any("current governance" in item for item in blocked.blockers)
    assert service.get(proposal_id)["status"] == LegislativeStatus.BLOCKED.value

    grant_law(repo)
    accepted = service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="Authority and evidence are now complete.",
    )
    assert accepted.promulgation_authorized
    assert service.get(proposal_id)["status"] == LegislativeStatus.ACCEPTED.value


def test_legislative_freeze_blocks_acceptance(tmp_path):
    repo = build_repo(tmp_path)
    admin = grant_law(repo)
    admin.impose_sanction(
        "chaos",
        SanctionType.FREEZE_LEGISLATIVE_BUDGET,
        reason="temporary freeze",
    )
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())

    review = service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="Review during freeze.",
    )
    assert not review.promulgation_authorized
    assert service.get(proposal_id)["status"] == LegislativeStatus.BLOCKED.value


def test_review_is_bound_to_persisted_pr_sha_base_and_check_set(tmp_path):
    repo = build_repo(tmp_path)
    grant_law(repo)
    service = DivineLegislationService(repo)
    source = dossier()
    proposal_id = service.submit("chaos", source)

    review = service.review(
        proposal_id,
        candidate(
            proposal_id,
            source,
            head_sha="c" * 40,
            required_checks=("python",),
            passed_checks=frozenset({"python"}),
        ),
        decision=CreatorDecision.ACCEPT,
        reason="Attempted review of a different revision.",
    )

    assert not review.promulgation_authorized
    assert any("head_sha" in blocker for blocker in review.blockers)
    assert any("required_checks" in blocker for blocker in review.blockers)
    assert service.get(proposal_id)["status"] == LegislativeStatus.BLOCKED.value


def test_only_father_can_review_or_promulgate(tmp_path):
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
    with pytest.raises(PermissionError, match="Father"):
        service.mark_promulgated(
            proposal_id,
            merge_commit="d" * 40,
            performed_by="chaos",
        )


def test_god_can_amend_blocked_law_but_not_accepted_law(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="Insufficient authority.",
    )
    amended = dossier(head_sha="c" * 40)
    service.amend("chaos", proposal_id, amended)
    assert service.get(proposal_id)["payload"]["head_sha"] == "c" * 40
    assert service.get(proposal_id)["status"] == LegislativeStatus.PROPOSED.value

    grant_law(repo)
    service.review(
        proposal_id,
        candidate(proposal_id, amended),
        decision=CreatorDecision.ACCEPT,
        reason="Amended law accepted.",
    )
    with pytest.raises(PermissionError):
        service.amend("chaos", proposal_id, dossier(head_sha="d" * 40))


def test_accept_then_promulgate_records_merge_and_terminal_state(tmp_path):
    repo = build_repo(tmp_path)
    grant_law(repo)
    service = DivineLegislationService(repo)
    proposal_id = service.submit("chaos", dossier())
    review = service.review(
        proposal_id,
        candidate(proposal_id),
        decision=CreatorDecision.ACCEPT,
        reason="All gates passed.",
    )
    assert review.promulgation_authorized

    service.mark_promulgated(proposal_id, merge_commit="d" * 40)
    stored = service.get(proposal_id)
    assert stored["status"] == LegislativeStatus.PROMULGATED.value
    assert stored["payload"]["merge_commit"] == "d" * 40
    assert stored["decided_by"] == "father"
    assert GovernanceStorage(repo).validate_audit_chain()

    with pytest.raises(PermissionError):
        service.review(
            proposal_id,
            candidate(proposal_id),
            decision=CreatorDecision.WAIT,
            reason="Cannot reopen history.",
        )
