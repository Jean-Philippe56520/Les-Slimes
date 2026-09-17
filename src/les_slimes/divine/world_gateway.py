from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .access import DivineAccessPolicy


@runtime_checkable
class CanonicalApiProvider(Protocol):
    """Authenticated API provider bound to one actor outside the model surface."""

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class DivineWorldGateway:
    """Typed access to canonical API routes without caller-controlled identity."""

    def __init__(self, actor_id: str, provider: CanonicalApiProvider) -> None:
        self.policy = DivineAccessPolicy(actor_id)
        self.actor_id = actor_id
        self.provider = provider

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.policy.assert_api_request(method, path)
        if body is not None and "actor_id" in body:
            raise PermissionError("actor_id is resolved by authentication, never by divine input")
        return self.provider.request(method, path, body=body, query=query)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def world(self) -> dict[str, Any]:
        return self._request("GET", "/world")

    def slimes(self) -> dict[str, Any]:
        return self._request("GET", "/world/slimes")

    def foods(self) -> dict[str, Any]:
        return self._request("GET", "/world/foods")

    def identity(self) -> dict[str, Any]:
        return self._request("GET", "/me")

    def governance(self) -> dict[str, Any]:
        return self._request("GET", "/governance")

    def journals(
        self, *, actor_id: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise ValueError("journal limit must be in [1, 500]")
        query: dict[str, Any] = {"limit": limit}
        if actor_id is not None:
            query["actor_id"] = actor_id
        return self._request("GET", "/journals", query=query)

    def proposals(
        self, *, actor_id: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        if not 1 <= limit <= 500:
            raise ValueError("proposal limit must be in [1, 500]")
        query: dict[str, Any] = {"limit": limit}
        if actor_id is not None:
            query["actor_id"] = actor_id
        return self._request("GET", "/proposals", query=query)

    def add_journal(
        self,
        *,
        entry_type: str,
        content: str,
        world_tick: int | None = None,
        intervention_id: str | None = None,
        git_commit: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "entry_type": entry_type,
            "content": content,
        }
        if world_tick is not None:
            body["world_tick"] = world_tick
        if intervention_id is not None:
            body["intervention_id"] = intervention_id
        if git_commit is not None:
            body["git_commit"] = git_commit
        if context is not None:
            body["context"] = context
        return self._request("POST", "/journals", body=body)

    def add_proposal(
        self,
        *,
        proposal_type: str,
        title: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/proposals",
            body={
                "proposal_type": proposal_type,
                "title": title,
                "payload": payload or {},
            },
        )

    def enqueue_command(
        self,
        *,
        command_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        source_proposal_id: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "command_type": command_type,
            "payload": payload,
            "idempotency_key": idempotency_key,
        }
        if source_proposal_id is not None:
            body["source_proposal_id"] = source_proposal_id
        return self._request("POST", "/commands", body=body)
