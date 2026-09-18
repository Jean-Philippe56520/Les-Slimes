from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from ..database.base import RelationalRepository
from ..runtime.storage import RuntimeStorage
from .archive_gateway import ArchiveProvider, DivineArchiveGateway
from .git_gateway import DivineGitGateway, ReadOnlyGitProvider
from .session_identity import DivineRequestMetadata, DivineSessionBindingService
from .world_gateway import CanonicalApiProvider, DivineWorldGateway


@runtime_checkable
class CanonicalApiProviderFactory(Protocol):
    """Creates an API client whose credential is already bound to one actor."""

    def for_actor(self, actor_id: str) -> CanonicalApiProvider: ...


class DivineActorGateway:
    """Session-bound tool surface for Order and Chaos.

    The caller never supplies actor_id. Identity is resolved from trusted request
    metadata and the persisted session binding before any actor-specific provider
    is selected.
    """

    def __init__(
        self,
        repository: RelationalRepository,
        *,
        git_provider: ReadOnlyGitProvider,
        archive_provider: ArchiveProvider,
        api_provider_factory: CanonicalApiProviderFactory,
    ) -> None:
        self.repository = repository
        self.sessions = DivineSessionBindingService(repository)
        self.runtime = RuntimeStorage(repository)
        self.git_provider = git_provider
        self.archive_provider = archive_provider
        self.api_provider_factory = api_provider_factory
        self._archive_gateways: dict[str, DivineArchiveGateway] = {}

    def _resolve_actor(self, meta: Mapping[str, Any]) -> str:
        request_meta = DivineRequestMetadata.from_meta(meta)
        binding = self.sessions.resolve(
            session_id=request_meta.session_id,
            subject_id=request_meta.subject_id,
        )
        if binding.actor_id not in {"order", "chaos"}:
            raise PermissionError("DIVINE_TOOL_SURFACE_REQUIRES_ORDER_OR_CHAOS")
        return binding.actor_id

    def identity_status(self, meta: Mapping[str, Any]) -> dict[str, Any]:
        request_meta = DivineRequestMetadata.from_meta(meta)
        binding = self.sessions.resolve(
            session_id=request_meta.session_id,
            subject_id=request_meta.subject_id,
        )
        actor = self.runtime.get_actor(binding.actor_id)
        result: dict[str, Any] = {
            "identity": actor.id,
            "display_name": actor.display_name,
            "kind": actor.kind,
            "status": "bound",
            "active": actor.active,
        }
        if actor.id in {"order", "chaos"}:
            archive = DivineArchiveGateway(actor.id, self.archive_provider)
            result["proposal_workspace_id"] = archive.policy.proposal_workspace_id
            result["git_access"] = "read_only"
        return result

    def _git(self, meta: Mapping[str, Any]) -> DivineGitGateway:
        return DivineGitGateway(self._resolve_actor(meta), self.git_provider)

    def _archive(self, meta: Mapping[str, Any]) -> DivineArchiveGateway:
        actor_id = self._resolve_actor(meta)
        gateway = self._archive_gateways.get(actor_id)
        if gateway is None:
            gateway = DivineArchiveGateway(actor_id, self.archive_provider)
            self._archive_gateways[actor_id] = gateway
        return gateway

    def _world(self, meta: Mapping[str, Any]) -> DivineWorldGateway:
        actor_id = self._resolve_actor(meta)
        provider = self.api_provider_factory.for_actor(actor_id)
        return DivineWorldGateway(actor_id, provider)

    # Registre des Lois — read only.
    def laws_main_sha(self, meta: Mapping[str, Any]) -> str:
        return self._git(meta).main_sha()

    def laws_read(
        self,
        meta: Mapping[str, Any],
        *,
        path: str,
        ref: str = "main",
    ) -> str:
        return self._git(meta).read_file(path, ref=ref)

    def laws_search(
        self,
        meta: Mapping[str, Any],
        *,
        query: str,
    ) -> list[dict]:
        return self._git(meta).search_code(query)

    # Grandes Archives.
    def archives_manifest(self, meta: Mapping[str, Any]) -> str:
        return self._archive(meta).read_manifest()

    def archives_search(
        self,
        meta: Mapping[str, Any],
        *,
        query: str,
        limit: int = 50,
    ):
        return self._archive(meta).search(query, limit=limit)

    def archives_search_proposals(
        self,
        meta: Mapping[str, Any],
        *,
        query: str,
        limit: int = 50,
    ):
        return self._archive(meta).search_proposals(query, limit=limit)

    def archives_read(self, meta: Mapping[str, Any], *, item_id: str) -> str:
        return self._archive(meta).read(item_id)

    def archives_create_proposal_text(
        self,
        meta: Mapping[str, Any],
        *,
        name: str,
        content: str,
    ):
        return self._archive(meta).create_proposal_text(name=name, content=content)

    # Portes du Monde.
    def world_observe(self, meta: Mapping[str, Any]) -> dict[str, Any]:
        return self._world(meta).world()

    def world_slimes(self, meta: Mapping[str, Any]) -> dict[str, Any]:
        return self._world(meta).slimes()

    def world_foods(self, meta: Mapping[str, Any]) -> dict[str, Any]:
        return self._world(meta).foods()

    def governance_status(self, meta: Mapping[str, Any]) -> dict[str, Any]:
        return self._world(meta).governance()

    def journal_append(
        self,
        meta: Mapping[str, Any],
        *,
        entry_type: str,
        content: str,
        world_tick: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._world(meta).add_journal(
            entry_type=entry_type,
            content=content,
            world_tick=world_tick,
            context=context,
        )

    def proposal_create(
        self,
        meta: Mapping[str, Any],
        *,
        proposal_type: str,
        title: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._world(meta).add_proposal(
            proposal_type=proposal_type,
            title=title,
            payload=payload,
        )
