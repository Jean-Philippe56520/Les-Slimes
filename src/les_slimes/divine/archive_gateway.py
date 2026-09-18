from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .access import (
    CREATOR_REVIEW_FOLDER_ID,
    DIVINE_WORKSHOPS_ROOT_ID,
    LES_SLIMES_DRIVE_MANIFEST_ID,
    LES_SLIMES_DRIVE_ROOT_ID,
    DivineAccessPolicy,
)


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
    """LES_SLIMES archive reader plus actor-owned proposal workshop writer."""

    def __init__(self, actor_id: str, provider: ArchiveProvider) -> None:
        self.policy = DivineAccessPolicy(actor_id)
        self.provider = provider
        self._readable_ids = {
            LES_SLIMES_DRIVE_ROOT_ID,
            LES_SLIMES_DRIVE_MANIFEST_ID,
            self.policy.proposal_workspace_id,
        }
        self._writable_ids: set[str] = set()

    def read_manifest(self) -> str:
        self.policy.assert_drive_manifest(LES_SLIMES_DRIVE_MANIFEST_ID)
        return self.provider.read_text(LES_SLIMES_DRIVE_MANIFEST_ID)

    def search(self, query: str, *, limit: int = 50) -> tuple[ArchiveItem, ...]:
        """Read-only search over all LES_SLIMES archives."""
        query = query.strip()
        if not query:
            raise ValueError("archive search query is required")
        if not 1 <= limit <= 200:
            raise ValueError("archive search limit must be in [1, 200]")
        items = self.provider.search_descendants(
            LES_SLIMES_DRIVE_ROOT_ID,
            query,
            limit=limit,
        )
        for item in items:
            if item.scope_root_id != LES_SLIMES_DRIVE_ROOT_ID:
                raise PermissionError("Archive provider returned an item outside LES_SLIMES")
        self._readable_ids.update(item.id for item in items)
        return tuple(items)

    def search_proposals(self, query: str, *, limit: int = 50) -> tuple[ArchiveItem, ...]:
        """Discover proposal artifacts writable by this god in its own workshop."""
        query = query.strip()
        if not query:
            raise ValueError("proposal search query is required")
        if not 1 <= limit <= 200:
            raise ValueError("proposal search limit must be in [1, 200]")
        workspace_id = self.policy.proposal_workspace_id
        items = self.provider.search_descendants(workspace_id, query, limit=limit)
        for item in items:
            if item.scope_root_id != workspace_id:
                raise PermissionError("Proposal provider returned an item outside this god's workshop")
        self._readable_ids.update(item.id for item in items)
        self._writable_ids.update(item.id for item in items)
        return tuple(items)

    def read(self, item_id: str) -> str:
        if item_id not in self._readable_ids:
            raise PermissionError(
                "Drive item is not an authorized LES_SLIMES capability; discover it through scoped search first"
            )
        return self.provider.read_text(item_id)

    def create_proposal_text(self, *, name: str, content: str) -> ArchiveItem:
        name = name.strip()
        if not name:
            raise ValueError("proposal artifact name is required")
        parent_id = self.policy.proposal_workspace_id
        self.policy.assert_drive_write_parent(parent_id)
        item = self.provider.create_text(parent_id, name=name, content=content)
        if item.scope_root_id != parent_id:
            raise PermissionError("Archive provider created an item outside this god's workshop")
        self._readable_ids.add(item.id)
        self._writable_ids.add(item.id)
        return item

    def update_proposal_text(self, item_id: str, *, content: str) -> None:
        if item_id not in self._writable_ids:
            raise PermissionError("A god may update only artifacts from its own proposal workshop")
        self.provider.update_text(item_id, content=content)


class CreatorArchiveGateway:
    """Creator view of divine workshops, still confined to LES_SLIMES."""

    def __init__(self, provider: ArchiveProvider) -> None:
        self.provider = provider
        self._readable_ids = {
            LES_SLIMES_DRIVE_MANIFEST_ID,
            DIVINE_WORKSHOPS_ROOT_ID,
            CREATOR_REVIEW_FOLDER_ID,
        }
        self._review_ids: set[str] = set()

    def search_proposals(self, query: str, *, limit: int = 100) -> tuple[ArchiveItem, ...]:
        query = query.strip()
        if not query:
            raise ValueError("proposal search query is required")
        if not 1 <= limit <= 200:
            raise ValueError("proposal search limit must be in [1, 200]")
        items = self.provider.search_descendants(DIVINE_WORKSHOPS_ROOT_ID, query, limit=limit)
        for item in items:
            if item.scope_root_id != DIVINE_WORKSHOPS_ROOT_ID:
                raise PermissionError("Creator workshop search escaped LES_SLIMES divine workshops")
        self._readable_ids.update(item.id for item in items)
        return tuple(items)

    def read(self, item_id: str) -> str:
        if item_id not in self._readable_ids:
            raise PermissionError("Creator must discover workshop artifacts through scoped search first")
        return self.provider.read_text(item_id)

    def create_review_text(self, *, name: str, content: str) -> ArchiveItem:
        name = name.strip()
        if not name:
            raise ValueError("review artifact name is required")
        item = self.provider.create_text(CREATOR_REVIEW_FOLDER_ID, name=name, content=content)
        if item.scope_root_id != CREATOR_REVIEW_FOLDER_ID:
            raise PermissionError("Review artifact escaped CREATOR_REVIEW")
        self._readable_ids.add(item.id)
        self._review_ids.add(item.id)
        return item

    def update_review_text(self, item_id: str, *, content: str) -> None:
        if item_id not in self._review_ids:
            raise PermissionError("Creator may update only review artifacts created in CREATOR_REVIEW")
        self.provider.update_text(item_id, content=content)
