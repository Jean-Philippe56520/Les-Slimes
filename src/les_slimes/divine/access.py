from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


AUTHORIZED_REPOSITORY = "Jean-Philippe56520/Les-Slimes"
LES_SLIMES_DRIVE_ROOT_ID = "1NzXVNZTIiEeiJCehBfdBNASk3-JRSHFc"
LES_SLIMES_DRIVE_MANIFEST_ID = "1F20p302TW9c4ANbbfvhg7OO0l4BBkpMquxxjVTcI91c"
DIVINE_WORKSHOPS_ROOT_ID = "1qNxcE9R0DewgB8iQPwFXaS2WXcz_fU1k"
ORDER_PROPOSALS_FOLDER_ID = "1VbYXIt8hU4UEAVYIvWMob7SL0G3-lcOC"
CHAOS_PROPOSALS_FOLDER_ID = "1i5L-8aOCvrwc3Buck3hhJnFydvlFXc2v"
CREATOR_REVIEW_FOLDER_ID = "1i0vMELFu0Ijw7ZhP4430GgZ3lq3TXArt"


class DivineSurface(StrEnum):
    GITHUB = "github"
    DRIVE = "drive"
    CANONICAL_API = "canonical_api"
    EXPERIMENT = "experiment"


_API_READ_PATHS = frozenset(
    {
        "/health",
        "/world",
        "/world/slimes",
        "/world/foods",
        "/me",
        "/governance",
        "/journals",
        "/proposals",
    }
)
_API_WRITE_PATHS = frozenset({"/commands", "/journals", "/proposals"})

_CREATOR_ONLY_READ_PATHS = frozenset(
    {
        "README.md",
        "docs/PROJECT_STATE.md",
        "docs/PROJECT_INSTRUCTIONS.md",
        "docs/DIVINE_AUTONOMY.md",
        "docs/DIVINE_GOVERNANCE.md",
        "docs/GOD_CREATOR_INSTRUCTIONS.md",
        "docs/OBSERVER_CONTRACT.md",
        "docs/SCIENTIFIC_PROTOCOL.md",
        "docs/API.md",
        "docs/PRODUCTION.md",
        "docs/FRONTEND.md",
    }
)
_CREATOR_ONLY_READ_PREFIXES = (
    "src/les_slimes/divine/",
    "tests/test_divine_",
    "tests/test_sovereign_",
    "tests/test_creator_promulgation",
)

_PROTECTED_LAW_PREFIXES = (
    ".github/",
    "deploy/",
    "docs/",
    "frontend/",
    "src/les_slimes/api/",
    "src/les_slimes/database/",
    "src/les_slimes/divine/",
    "src/les_slimes/governance/",
    "src/les_slimes/runtime/",
)
_PROTECTED_LAW_PATHS = frozenset(
    {
        "README.md",
        "Dockerfile",
        "netlify.toml",
        "pyproject.toml",
        "src/les_slimes/cli.py",
        "src/les_slimes/production.py",
    }
)
_PROTECTED_TEST_PREFIXES = (
    "tests/test_api",
    "tests/test_auth",
    "tests/test_creator_",
    "tests/test_database",
    "tests/test_divine_",
    "tests/test_governance",
    "tests/test_postgres",
    "tests/test_production",
    "tests/test_runtime",
    "tests/test_sovereign_",
    "tests/test_worker",
)


@dataclass(frozen=True, slots=True)
class DivineAccessPolicy:
    """Fail-closed capability policy for Order and Chaos.

    GitHub is deliberately read-only for divine actors. Proposed source changes are
    prepared in an isolated experiment/workspace and exported into the actor's Drive
    workshop. Only the Creator is allowed to create Git branches, commits or pull requests.
    """

    actor_id: str

    def __post_init__(self) -> None:
        if self.actor_id not in {"order", "chaos"}:
            raise ValueError("DivineAccessPolicy is restricted to Order and Chaos")

    @property
    def own_instruction_path(self) -> str:
        name = "ORDER" if self.actor_id == "order" else "CHAOS"
        return f"docs/GOD_{name}_INSTRUCTIONS.md"

    @property
    def proposal_workspace_id(self) -> str:
        return (
            ORDER_PROPOSALS_FOLDER_ID
            if self.actor_id == "order"
            else CHAOS_PROPOSALS_FOLDER_ID
        )

    def assert_surface(self, surface: str | DivineSurface) -> DivineSurface:
        try:
            value = surface if isinstance(surface, DivineSurface) else DivineSurface(surface)
        except ValueError as exc:
            raise PermissionError(f"Surface {surface!r} is outside the divine perimeter") from exc
        return value

    def assert_repository(self, repository_full_name: str) -> None:
        if repository_full_name != AUTHORIZED_REPOSITORY:
            raise PermissionError("Only the Les Slimes repository is authorized")

    def assert_repo_path(self, path: str) -> str:
        if not path or "\" in path:
            raise PermissionError("Invalid repository path")
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise PermissionError("Repository path escapes the authorized workspace")
        return candidate.as_posix()

    def can_divine_read_path(self, path: str) -> bool:
        try:
            safe = self.assert_repo_path(path)
        except PermissionError:
            return False
        if safe in _CREATOR_ONLY_READ_PATHS:
            return False
        if safe.startswith(_CREATOR_ONLY_READ_PREFIXES):
            return False
        if safe in {
            "docs/GOD_ORDER_INSTRUCTIONS.md",
            "docs/GOD_CHAOS_INSTRUCTIONS.md",
        }:
            return safe == self.own_instruction_path
        return True

    def assert_divine_read_path(self, path: str) -> str:
        safe = self.assert_repo_path(path)
        if not self.can_divine_read_path(safe):
            raise PermissionError("Repository path is outside this god's knowledge surface")
        return safe

    def assert_git_read_only(self) -> None:
        """Document the hard capability rule used by adapters and tests."""
        return None

    def assert_law_target_path(self, path: str) -> str:
        """Validate a file that may be proposed for an ordinary divine Law.

        This does not grant Git write permission to the god. It only defines the maximum
        implementation surface the Creator may choose to realize from a divine proposal.
        """

        safe = self.assert_repo_path(path)
        if safe in _PROTECTED_LAW_PATHS or safe.startswith(_PROTECTED_LAW_PREFIXES):
            raise PermissionError("A divine Law cannot target protected world infrastructure")
        if safe.startswith(_PROTECTED_TEST_PREFIXES):
            raise PermissionError("A divine Law cannot target tests protecting world infrastructure")
        if safe.startswith("tests/") or safe.startswith("src/les_slimes/") or safe.startswith("config/"):
            return safe
        raise PermissionError("A divine Law may target only engine/config/test surfaces")

    def assert_drive_lineage(self, ancestor_ids: tuple[str, ...] | list[str]) -> None:
        if LES_SLIMES_DRIVE_ROOT_ID not in ancestor_ids:
            raise PermissionError("Drive item is outside the LES_SLIMES archive")

    def assert_drive_manifest(self, manifest_id: str) -> None:
        if manifest_id != LES_SLIMES_DRIVE_MANIFEST_ID:
            raise PermissionError("Only the canonical LES_SLIMES manifest is authorized")

    def assert_drive_write_parent(self, parent_id: str) -> None:
        if parent_id != self.proposal_workspace_id:
            raise PermissionError("A god may write only inside its own proposal workshop")

    def assert_api_request(self, method: str, path: str) -> None:
        normalized_method = method.upper().strip()
        normalized_path = path.rstrip("/") or "/"
        if normalized_path.startswith("/admin"):
            raise PermissionError("Divine actors cannot access Creator administration routes")
        if normalized_method == "GET" and normalized_path in _API_READ_PATHS:
            return
        if normalized_method == "POST" and normalized_path in _API_WRITE_PATHS:
            return
        raise PermissionError(
            f"API request {normalized_method} {normalized_path} is outside the divine allowlist"
        )
