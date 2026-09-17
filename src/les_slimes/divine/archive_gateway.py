from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .access import LES_SLIMES_DRIVE_MANIFEST_ID, LES_SLIMES_DRIVE_ROOT_ID, DivineAccessPolicy


@dataclass(frozen=True, slots=True)
class ArchiveItem:
    id: str
    name: str
    mime_type: str
    scope_root_id: str


@runtime_checkable
class ArchiveProvider(Protocol):
    """Drive-like provider already restricted by deployment credentials."""

    def search_descendants(
        self, root_id: str, query: str, *, limit: int
    ) -> list[ArchiveItem]: ...

    def read_text(self, item_id: str) -> str: ...

    def create_text(self, parent_id: str, *, name: str, content: str) -> ArchiveItem: ...

    def update_text(self, item_id: str, *, content: str) -> None: ...


class DivineArchiveGateway:
    """Capability gateway for the LES_SLIMES archive only.

    Gods cannot present an arbitrary Drive ID and ask the provider to inspect it. An item
    must first be obtained through the root-scoped search, except for the canonical root
    and manifest which are seeded capabilities.
    """

    def __init__(self, actor_id: str, provider: ArchiveProvider) -> None:
        self.policy = DivineAccessPolicy(actor_id)
        self.provider = provider
        self._authorized_ids = {
            LES_SLIMES_DRIVE_ROOT_ID,
            LES_SLIMES_DRIVE_MANIFEST_ID,
        }

    def read_manifest(self) -> str:
        self.policy.assert_drive_manifest(LES_SLIMES_DRIVE_MANIFEST_ID)
        return self.provider.read_text(LES_SLIMES_DRIVE_MANIFEST_ID)

    def search(self, query: str, *, limit: int = 50) -> tuple[ArchiveItem, ...]:
        if not query.strip():
            raise ValueError("archive search query is required")
        if not 1 <= limit <= 200:
            raise ValueError("archive search limit must be in [1, 200]")
        items = self.provider.search_descendants(
            LES_SLIMES_DRIVE_ROOT_ID,
            query.strip(),
            limit=limit,
        )
        for item in items:
            if item.scope_root_id != LES_SLIMES_DRIVE_ROOT_ID:
                raise PermissionError("Archive provider returned an item outside LES_SLIMES")
        self._authorized_ids.update(item.id for item in items)
        return tuple(items)

    def read(self, item_id: str) -> str:
        self._assert_capability(item_id)
        return self.provider.read_text(item_id)

    def create_text(self, parent_id: str, *, name: str, content: str) -> ArchiveItem:
        self._assert_capability(parent_id)
        if not name.strip():
            raise ValueError("archive item name is required")
        item = self.provider.create_text(parent_id, name=name.strip(), content=content)
        if item.scope_root_id != LES_SLIMES_DRIVE_ROOT_ID:
            raise PermissionError("Archive provider created an item outside LES_SLIMES")
        self._authorized_ids.add(item.id)
        return item

    def update_text(self, item_id: str, *, content: str) -> None:
        self._assert_capability(item_id)
        self.provider.update_text(item_id, content=content)

    def _assert_capability(self, item_id: str) -> None:
        if item_id not in self._authorized_ids:
            raise PermissionError(
                "Drive item is not an authorized LES_SLIMES capability; discover it through scoped search first"
            )
