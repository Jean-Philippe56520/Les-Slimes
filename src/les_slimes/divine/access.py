from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


AUTHORIZED_REPOSITORY = "Jean-Philippe56520/Les-Slimes"
LES_SLIMES_DRIVE_ROOT_ID = "1NzXVNZTIiEeiJCehBfdBNASk3-JRSHFc"
LES_SLIMES_DRIVE_MANIFEST_ID = "1F20p302TW9c4ANbbfvhg7OO0l4BBkpMquxxjVTcI91c"


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

# Operational texts used by the Creator and maintainers are deliberately not part of a
# god's knowledge surface. This is an epistemic boundary, not secrecy for credentials.
_CREATOR_ONLY_READ_PATHS = frozenset(
    {
        "README.md",
        "docs/PROJECT_STATE.md",
        "docs/PROJECT_INSTRUCTIONS.md",
        "docs/DIVINE_AUTONOMY.md",
        "docs/DIVINE_GOVERNANCE.md",
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

# A divine Law can change the artificial-life domain, never the mechanisms that define
# identity, governance, canonical persistence, deployment or the divine boundary itself.
_PROTECTED_WRITE_PREFIXES = (
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
_PROTECTED_WRITE_PATHS = frozenset(
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

    Adapters must call this policy before touching GitHub, Drive, the canonical API or an
    experiment workspace. Repository, archive root, knowledge boundary and protected-law
    surface are server-side policy, never parameters controlled by a god.
    """

    actor_id: str

    def __post_init__(self) -> None:
        if self.actor_id not in {"order", "chaos"}:
            raise ValueError("DivineAccessPolicy is restricted to Order and Chaos")

    @property
    def branch_prefix(self) -> str:
        return f"god/{self.actor_id}/"

    @property
    def own_instruction_path(self) -> str:
        name = "ORDER" if self.actor_id == "order" else "CHAOS"
        return f"docs/GOD_{name}_INSTRUCTIONS.md"

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
        if not path or "\\" in path:
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

    def assert_divine_write_path(self, path: str) -> str:
        safe = self.assert_repo_path(path)
        if safe in _PROTECTED_WRITE_PATHS or safe.startswith(_PROTECTED_WRITE_PREFIXES):
            raise PermissionError("A divine Law cannot modify protected world infrastructure")
        if safe.startswith(_PROTECTED_TEST_PREFIXES):
            raise PermissionError("A divine Law cannot modify tests protecting world infrastructure")
        if safe.startswith("tests/") or safe.startswith("src/les_slimes/") or safe.startswith("config/"):
            return safe
        raise PermissionError("A divine Law may modify only engine/config/test surfaces")

    def assert_git_write_branch(self, branch: str) -> None:
        if not branch.startswith(self.branch_prefix) or branch == self.branch_prefix:
            raise PermissionError(
                f"{self.actor_id} may write only to branches under {self.branch_prefix}"
            )

    def assert_drive_lineage(self, ancestor_ids: tuple[str, ...] | list[str]) -> None:
        if LES_SLIMES_DRIVE_ROOT_ID not in ancestor_ids:
            raise PermissionError("Drive item is outside the LES_SLIMES archive")

    def assert_drive_manifest(self, manifest_id: str) -> None:
        if manifest_id != LES_SLIMES_DRIVE_MANIFEST_ID:
            raise PermissionError("Only the canonical LES_SLIMES manifest is authorized")

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
