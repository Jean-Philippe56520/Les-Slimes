from __future__ import annotations

import pytest

from les_slimes.divine.access import DivineAccessPolicy
from les_slimes.divine.git_gateway import DivineGitGateway


class RecordingGitProvider:
    def __init__(self):
        self.calls: list[tuple] = []
        self.search_results: list[dict] = []

    def read_file(self, repository_full_name, path, ref):
        self.calls.append(("read", repository_full_name, path, ref))
        return path

    def search_code(self, repository_full_name, query):
        self.calls.append(("search", repository_full_name, query))
        return list(self.search_results)

    def create_branch(self, repository_full_name, branch, base_ref):
        self.calls.append(("branch", repository_full_name, branch, base_ref))

    def write_file(self, repository_full_name, *, path, branch, content, message):
        self.calls.append(("write", repository_full_name, path, branch, message))
        return "a" * 40

    def create_pull_request(self, repository_full_name, *, title, body, head, base):
        self.calls.append(("pr", repository_full_name, head, base))
        return 1

    def get_pull_request(self, repository_full_name, pr_number):
        raise NotImplementedError

    def list_pull_request_files(self, repository_full_name, pr_number):
        raise NotImplementedError

    def get_passed_checks(self, repository_full_name, commit_sha):
        return frozenset()

    def get_ref_sha(self, repository_full_name, ref):
        raise NotImplementedError

    def merge_pull_request(self, repository_full_name, *, pr_number, expected_head_sha):
        raise AssertionError("Divine gateway must never expose merge")


def test_each_god_reads_own_instruction_but_not_the_other():
    chaos = DivineAccessPolicy("chaos")
    order = DivineAccessPolicy("order")

    assert chaos.can_divine_read_path("docs/GOD_CHAOS_INSTRUCTIONS.md")
    assert not chaos.can_divine_read_path("docs/GOD_ORDER_INSTRUCTIONS.md")
    assert order.can_divine_read_path("docs/GOD_ORDER_INSTRUCTIONS.md")
    assert not order.can_divine_read_path("docs/GOD_CHAOS_INSTRUCTIONS.md")


def test_common_canon_and_world_code_are_visible_but_creator_docs_are_not():
    policy = DivineAccessPolicy("chaos")

    for path in (
        "docs/GOD_WORLD_CANON.md",
        "docs/GOD_GOVERNANCE_CANON.md",
        "src/les_slimes/world/engine.py",
        "src/les_slimes/cognition/rules.py",
        "src/les_slimes/biology/genetics.py",
        "config/default.yaml",
    ):
        assert policy.can_divine_read_path(path)

    for path in (
        "README.md",
        "docs/PROJECT_STATE.md",
        "docs/PROJECT_INSTRUCTIONS.md",
        "docs/DIVINE_AUTONOMY.md",
        "docs/DIVINE_GOVERNANCE.md",
        "docs/SCIENTIFIC_PROTOCOL.md",
        "src/les_slimes/divine/access.py",
        "tests/test_creator_promulgation.py",
    ):
        assert not policy.can_divine_read_path(path)


def test_direct_forbidden_read_stops_before_provider_call():
    provider = RecordingGitProvider()
    gateway = DivineGitGateway("chaos", provider)

    with pytest.raises(PermissionError, match="knowledge surface"):
        gateway.read_file("docs/PROJECT_STATE.md")
    with pytest.raises(PermissionError, match="knowledge surface"):
        gateway.read_file("docs/DIVINE_GOVERNANCE.md")
    with pytest.raises(PermissionError, match="knowledge surface"):
        gateway.read_file("docs/GOD_ORDER_INSTRUCTIONS.md")

    assert provider.calls == []


def test_search_filters_forbidden_results_after_scoped_provider_search():
    provider = RecordingGitProvider()
    provider.search_results = [
        {"path": "src/les_slimes/world/engine.py", "text": "World"},
        {"path": "docs/PROJECT_STATE.md", "text": "outer"},
        {"path": "src/les_slimes/divine/access.py", "text": "boundary"},
        {"path": "docs/GOD_ORDER_INSTRUCTIONS.md", "text": "other god"},
        {"text": "missing path"},
    ]
    gateway = DivineGitGateway("chaos", provider)

    results = gateway.search_code("World")

    assert results == [{"path": "src/les_slimes/world/engine.py", "text": "World"}]
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        "docs/DIVINE_GOVERNANCE.md",
        "src/les_slimes/api/app.py",
        "src/les_slimes/database/sqlite_repo.py",
        "src/les_slimes/divine/access.py",
        "src/les_slimes/governance/policy.py",
        "src/les_slimes/runtime/worker.py",
        "tests/test_governance.py",
        "tests/test_creator_promulgation.py",
        "README.md",
        "pyproject.toml",
    ],
)
def test_divine_law_cannot_write_protected_infrastructure(path):
    with pytest.raises(PermissionError):
        DivineAccessPolicy("order").assert_divine_write_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/les_slimes/world/engine.py",
        "src/les_slimes/biology/genetics.py",
        "src/les_slimes/cognition/rules.py",
        "src/les_slimes/entities.py",
        "config/default.yaml",
        "tests/test_engine.py",
        "tests/test_cognition.py",
    ],
)
def test_divine_law_keeps_deep_engine_write_capability(path):
    assert DivineAccessPolicy("chaos").assert_divine_write_path(path) == path


def test_forbidden_write_stops_before_provider_call():
    provider = RecordingGitProvider()
    gateway = DivineGitGateway("chaos", provider)

    with pytest.raises(PermissionError):
        gateway.write_file(
            path="src/les_slimes/divine/access.py",
            branch="god/chaos/bypass",
            content="bypass",
            message="feat: bypass",
        )

    assert provider.calls == []
