from __future__ import annotations

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.divine import (
    CreatorDecision,
    CreatorImplementation,
    CreatorPromulgationService,
    DivineGitGateway,
    DivineLegislationService,
    GitMergeResult,
    LawCandidate,
    LawDossier,
    MergeAuthorization,
    PromulgationBlocked,
    PullRequestSnapshot,
)
from les_slimes.divine.access import AUTHORIZED_REPOSITORY
from les_slimes.divine.git_gateway import CreatorGitGateway
from les_slimes.governance.models import BudgetKind, PowerLevel, SanctionType
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.governance.storage import GovernanceStorage
from les_slimes.world.engine import World


SOURCE = "a" * 40
HEAD = "b" * 40
MERGE = "d" * 40
MANIFEST = "e" * 64
PATCH = "f" * 64


class FakeGitProvider:
    def __init__(self):
        self.calls: list[tuple] = []
        self.main_sha = SOURCE
        self.snapshot = PullRequestSnapshot(
            number=61,
            head_branch="father/law-1-niches",
            head_sha=HEAD,
            base_branch="main",
            base_sha=SOURCE,
            state="open",
            mergeable=True,
        )
        self.changed_files = (
            "src/les_slimes/world/engine.py",
            "tests/test_engine.py",
        )
        self.passed = frozenset({"python", "postgres", "docker"})
        self.merge_result = GitMergeResult(True, MERGE, "merged")
        self.raise_on_merge: Exception | None = None

    def _call(self, name, repository_full_name, *extra):
        self.calls.append((name, repository_full_name, *extra))
        assert repository_full_name == AUTHORIZED_REPOSITORY

    def read_file(self, repository_full_name, path, ref):
        self._call("read_file", repository_full_name, path, ref)
        return "content"

    def search_code(self, repository_full_name, query):
        self._call("search_code", repository_full_name, query)
        return [{"path": "src/les_slimes/world/engine.py"}]

    def create_branch(self, repository_full_name, branch, base_ref):
        self._call("create_branch", repository_full_name, branch, base_ref)

    def write_file(self, repository_full_name, *, path, branch, content, message):
        self._call("write_file", repository_full_name, path, branch, message)
        return HEAD

    def create_pull_request(self, repository_full_name, *, title, body, head, base):
        self._call("create_pull_request", repository_full_name, head, base)
        return 61

    def get_pull_request(self, repository_full_name, pr_number):
        self._call("get_pull_request", repository_full_name, pr_number)
        return self.snapshot

    def list_pull_request_files(self, repository_full_name, pr_number):
        self._call("list_pull_request_files", repository_full_name, pr_number)
        return self.changed_files

    def get_passed_checks(self, repository_full_name, commit_sha):
        self._call("get_passed_checks", repository_full_name, commit_sha)
        return self.passed

    def get_ref_sha(self, repository_full_name, ref):
        self._call("get_ref_sha", repository_full_name, ref)
        return self.main_sha

    def merge_pull_request(self, repository_full_name, *, pr_number, expected_head_sha):
        self._call("merge_pull_request", repository_full_name, pr_number, expected_head_sha)
        if self.raise_on_merge is not None:
            raise self.raise_on_merge
        if self.merge_result.merged:
            self.snapshot = PullRequestSnapshot(
                number=self.snapshot.number,
                head_branch=self.snapshot.head_branch,
                head_sha=self.snapshot.head_sha,
                base_branch=self.snapshot.base_branch,
                base_sha=self.snapshot.base_sha,
                state="closed",
                mergeable=False,
                merged=True,
                merge_commit_sha=self.merge_result.merge_commit_sha,
            )
        return self.merge_result


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=1201,
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


def grant_law(repo, *, budget=2):
    admin = GovernanceAdminService(repo)
    admin.set_power_level("chaos", PowerLevel.LAW, reason="promulgation test")
    admin.adjust_budget(
        "chaos", BudgetKind.LEGISLATIVE, budget, reason="promulgation test allocation"
    )
    return admin


def law_dossier():
    return LawDossier(
        title="Niche law",
        observation="Strategies are converging.",
        hypothesis="Bounded variation may preserve alternatives.",
        expected_benefit="Maintain viable alternatives.",
        risk="Variation can add noise.",
        source_main_sha=SOURCE,
        drive_artifact_id="drive-law-61",
        manifest_digest=MANIFEST,
        patch_digest=PATCH,
        affected_files=(
            "src/les_slimes/world/engine.py",
            "tests/test_engine.py",
        ),
        evidence=("EXP-1",),
        experiment_refs=("EXP-1",),
    )


def accepted_law(repo):
    grant_law(repo)
    legislation = DivineLegislationService(repo)
    dossier = law_dossier()
    proposal_id = legislation.submit("chaos", dossier)
    review = legislation.review(
        proposal_id,
        LawCandidate(
            actor_id="chaos",
            proposal_id=proposal_id,
            source_main_sha=dossier.source_main_sha,
            main_is_current=True,
            drive_artifact_id=dossier.drive_artifact_id,
            manifest_digest=dossier.manifest_digest,
            patch_digest=dossier.patch_digest,
            affected_files=dossier.affected_files,
            artifact_verified=True,
            patch_verified=True,
            governance_eligible=False,
            evidence_complete=True,
        ),
        decision=CreatorDecision.ACCEPT,
        reason="All evidence is sufficient for sovereign acceptance.",
    )
    assert review.implementation_authorized
    implementation = CreatorImplementation(
        proposal_id=proposal_id,
        candidate_actor_id="chaos",
        branch=f"father/law-{proposal_id}-niches",
        pr_number=61,
        head_sha=HEAD,
        base_sha=SOURCE,
        implemented_files=dossier.affected_files,
        required_checks=("python", "postgres", "docker"),
    )
    legislation.attach_creator_implementation(proposal_id, implementation)
    return proposal_id


def test_divine_git_gateway_is_read_only_but_creator_can_prepare_git_work():
    provider = FakeGitProvider()
    divine = DivineGitGateway("chaos", provider)
    divine.read_file("src/les_slimes/world/engine.py")
    divine.search_code("World")
    divine.main_sha()
    assert not hasattr(divine, "create_branch")
    assert not hasattr(divine, "write_file")
    assert not hasattr(divine, "open_law_pr")

    creator = CreatorGitGateway(provider)
    branch = creator.create_implementation_branch(1, "niches")
    creator.write_file(
        path="src/les_slimes/world/engine.py",
        branch=branch,
        content="content",
        message="feat: implement accepted law",
    )
    creator.open_law_pr(title="Law", body="Creator implementation", branch=branch)
    assert branch == "father/law-1-niches"


def test_creator_gateway_rejects_forged_repository_authorization():
    provider = FakeGitProvider()
    gateway = CreatorGitGateway(provider)
    forged = MergeAuthorization(
        repository_full_name="someone/else",
        branch="father/law-1-niches",
        pr_number=61,
        expected_head_sha=HEAD,
        expected_base_sha=SOURCE,
        candidate_actor_id="chaos",
        proposal_id=1,
    )
    with pytest.raises(PermissionError):
        gateway.merge(forged)
    assert not any(call[0] == "merge_pull_request" for call in provider.calls)


def test_creator_promulgation_reserves_budget_merges_and_finalizes(tmp_path):
    repo = build_repo(tmp_path)
    proposal_id = accepted_law(repo)
    provider = FakeGitProvider()
    provider.snapshot = PullRequestSnapshot(
        number=61,
        head_branch=f"father/law-{proposal_id}-niches",
        head_sha=HEAD,
        base_branch="main",
        base_sha=SOURCE,
        state="open",
        mergeable=True,
    )
    before = GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE)
    result = CreatorPromulgationService(repo, provider).promulgate(proposal_id)
    assert result.merge_commit_sha == MERGE
    stored = DivineLegislationService(repo).get(proposal_id)
    assert stored["status"] == "promulgated"
    assert stored["payload"]["promulgation"]["state"] == "completed"
    assert GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE) == before - 1
    assert len([call for call in provider.calls if call[0] == "merge_pull_request"]) == 1


def test_pr_file_scope_drift_blocks_before_budget_or_merge(tmp_path):
    repo = build_repo(tmp_path)
    proposal_id = accepted_law(repo)
    provider = FakeGitProvider()
    provider.snapshot = PullRequestSnapshot(
        number=61,
        head_branch=f"father/law-{proposal_id}-niches",
        head_sha=HEAD,
        base_branch="main",
        base_sha=SOURCE,
        state="open",
        mergeable=True,
    )
    provider.changed_files = ("src/les_slimes/world/engine.py",)
    before = GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE)
    with pytest.raises(PromulgationBlocked, match="file set differs"):
        CreatorPromulgationService(repo, provider).promulgate(proposal_id)
    assert GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE) == before


def test_drift_after_creator_implementation_blocks_before_budget_debit(tmp_path):
    repo = build_repo(tmp_path)
    proposal_id = accepted_law(repo)
    provider = FakeGitProvider()
    provider.snapshot = PullRequestSnapshot(
        number=61,
        head_branch=f"father/law-{proposal_id}-niches",
        head_sha=HEAD,
        base_branch="main",
        base_sha=SOURCE,
        state="open",
        mergeable=True,
    )
    provider.main_sha = "c" * 40
    before = GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE)
    with pytest.raises(PromulgationBlocked, match="main changed"):
        CreatorPromulgationService(repo, provider).promulgate(proposal_id)
    assert GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE) == before


def test_governance_revocation_after_acceptance_blocks_promulgation(tmp_path):
    repo = build_repo(tmp_path)
    proposal_id = accepted_law(repo)
    GovernanceAdminService(repo).impose_sanction(
        "chaos", SanctionType.SUSPEND, reason="Creator suspended Chaos before promulgation"
    )
    provider = FakeGitProvider()
    provider.snapshot = PullRequestSnapshot(
        number=61,
        head_branch=f"father/law-{proposal_id}-niches",
        head_sha=HEAD,
        base_branch="main",
        base_sha=SOURCE,
        state="open",
        mergeable=True,
    )
    before = GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE)
    with pytest.raises(PromulgationBlocked, match="governance"):
        CreatorPromulgationService(repo, provider).promulgate(proposal_id)
    assert GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE) == before


def test_unknown_merge_outcome_is_reconciled_without_double_debit(tmp_path):
    repo = build_repo(tmp_path)
    proposal_id = accepted_law(repo)
    provider = FakeGitProvider()
    provider.snapshot = PullRequestSnapshot(
        number=61,
        head_branch=f"father/law-{proposal_id}-niches",
        head_sha=HEAD,
        base_branch="main",
        base_sha=SOURCE,
        state="open",
        mergeable=True,
    )
    provider.raise_on_merge = TimeoutError("connection lost")
    before = GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE)
    service = CreatorPromulgationService(repo, provider)
    with pytest.raises(TimeoutError):
        service.promulgate(proposal_id)
    assert GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE) == before - 1

    provider.raise_on_merge = None
    provider.snapshot = PullRequestSnapshot(
        number=61,
        head_branch=f"father/law-{proposal_id}-niches",
        head_sha=HEAD,
        base_branch="main",
        base_sha=SOURCE,
        state="closed",
        mergeable=False,
        merged=True,
        merge_commit_sha=MERGE,
    )
    reconciled = service.promulgate(proposal_id)
    assert reconciled.reconciled
    assert GovernanceStorage(repo).budget_balance("chaos", BudgetKind.LEGISLATIVE) == before - 1
