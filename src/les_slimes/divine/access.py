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


@dataclass(frozen=True, slots=True)
class DivineAccessPolicy:
    """Fail-closed capability policy for Order and Chaos.

    This class is intentionally independent from connector implementations. Adapters must
    call it before touching GitHub, Drive, the canonical API or an experiment workspace.
    The repository and Drive root are constants rather than caller-controlled parameters.
    """

    actor_id: str

    def __post_init__(self) -> None:
        if self.actor_id not in {"order", "chaos"}:
            raise ValueError("DivineAccessPolicy is restricted to Order and Chaos")

    @property
    def branch_prefix(self) -> str:
        return f"god/{self.actor_id}/"

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
