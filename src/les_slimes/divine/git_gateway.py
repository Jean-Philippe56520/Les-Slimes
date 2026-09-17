from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .access import AUTHORIZED_REPOSITORY, DivineAccessPolicy
from .sovereign import MergeAuthorization


@dataclass(frozen=True, slots=True)
class PullRequestSnapshot:
    number: int
    head_branch: str
    head_sha: str
    base_branch: str
    base_sha: str
    state: str
    mergeable: bool
    merged: bool = False
    merge_commit_sha: str | None = None


@dataclass(frozen=True, slots=True)
class GitMergeResult:
    merged: bool
    merge_commit_sha: str | None
    message: str = ""


@runtime_checkable
class GitProvider(Protocol):
    """Provider contract implemented outside the divine reasoning surface."""

    def read_file(self, repository_full_name: str, path: str, ref: str) -> str: ...

    def search_code(self, repository_full_name: str, query: str) -> list[dict]: ...

    def create_branch(
        self, repository_full_name: str, branch: str, base_ref: str
    ) -> None: ...

    def write_file(
        self,
        repository_full_name: str,
        *,
        path: str,
        branch: str,
        content: str,
        message: str,
    ) -> str: ...

    def create_pull_request(
        self,
        repository_full_name: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> int: ...

    def get_pull_request(
        self, repository_full_name: str, pr_number: int
    ) -> PullRequestSnapshot: ...

    def list_pull_request_files(
        self, repository_full_name: str, pr_number: int
    ) -> tuple[str, ...]: ...

    def get_passed_checks(
        self, repository_full_name: str, commit_sha: str
    ) -> frozenset[str]: ...

    def get_ref_sha(self, repository_full_name: str, ref: str) -> str: ...

    def merge_pull_request(
        self,
        repository_full_name: str,
        *,
        pr_number: int,
        expected_head_sha: str,
    ) -> GitMergeResult: ...


class DivineGitGateway:
    """Deep Git workspace constrained to one god's authorized knowledge and law surface."""

    def __init__(self, actor_id: str, provider: GitProvider) -> None:
        self.policy = DivineAccessPolicy(actor_id)
        self.provider = provider

    def read_file(self, path: str, *, ref: str = "main") -> str:
        safe_path = self.policy.assert_divine_read_path(path)
        return self.provider.read_file(AUTHORIZED_REPOSITORY, safe_path, ref)

    def search_code(self, query: str) -> list[dict]:
        if not query.strip():
            raise ValueError("search query is required")
        results = self.provider.search_code(AUTHORIZED_REPOSITORY, query)
        visible: list[dict] = []
        for result in results:
            path = result.get("path")
            if not isinstance(path, str):
                continue
            if self.policy.can_divine_read_path(path):
                visible.append(result)
        return visible

    def create_branch(self, slug: str, *, base_ref: str = "main") -> str:
        slug = slug.strip().strip("/")
        if not slug or "/" in slug or slug in {".", ".."}:
            raise ValueError("branch slug must be one non-empty path segment")
        branch = f"{self.policy.branch_prefix}{slug}"
        self.policy.assert_git_write_branch(branch)
        if base_ref != "main":
            raise PermissionError("Divine law branches must start from main")
        self.provider.create_branch(AUTHORIZED_REPOSITORY, branch, "main")
        return branch

    def write_file(
        self,
        *,
        path: str,
        branch: str,
        content: str,
        message: str,
    ) -> str:
        self.policy.assert_git_write_branch(branch)
        safe_path = self.policy.assert_divine_write_path(path)
        if not message.strip():
            raise ValueError("commit message is required")
        return self.provider.write_file(
            AUTHORIZED_REPOSITORY,
            path=safe_path,
            branch=branch,
            content=content,
            message=message.strip(),
        )

    def open_law_pr(self, *, title: str, body: str, branch: str) -> int:
        self.policy.assert_git_write_branch(branch)
        if not title.strip():
            raise ValueError("pull request title is required")
        return self.provider.create_pull_request(
            AUTHORIZED_REPOSITORY,
            title=title.strip(),
            body=body,
            head=branch,
            base="main",
        )

    def pull_request(self, pr_number: int) -> PullRequestSnapshot:
        if pr_number < 1:
            raise ValueError("pr_number must be positive")
        return self.provider.get_pull_request(AUTHORIZED_REPOSITORY, pr_number)

    def passed_checks(self, commit_sha: str) -> frozenset[str]:
        return self.provider.get_passed_checks(AUTHORIZED_REPOSITORY, commit_sha)


class CreatorGitGateway:
    """Sovereign Git operations. Merge requires an immutable authorization object."""

    def __init__(self, provider: GitProvider) -> None:
        self.provider = provider

    def main_sha(self) -> str:
        return self.provider.get_ref_sha(AUTHORIZED_REPOSITORY, "main")

    def pull_request(self, pr_number: int) -> PullRequestSnapshot:
        return self.provider.get_pull_request(AUTHORIZED_REPOSITORY, pr_number)

    def pull_request_files(self, pr_number: int) -> tuple[str, ...]:
        return self.provider.list_pull_request_files(AUTHORIZED_REPOSITORY, pr_number)

    def passed_checks(self, commit_sha: str) -> frozenset[str]:
        return self.provider.get_passed_checks(AUTHORIZED_REPOSITORY, commit_sha)

    def merge(self, authorization: MergeAuthorization) -> GitMergeResult:
        if authorization.repository_full_name != AUTHORIZED_REPOSITORY:
            raise PermissionError("Merge authorization targets an unauthorized repository")
        if authorization.authorized_by != "father":
            raise PermissionError("Only a Father authorization can promulgate a Law")
        return self.provider.merge_pull_request(
            AUTHORIZED_REPOSITORY,
            pr_number=authorization.pr_number,
            expected_head_sha=authorization.expected_head_sha,
        )
