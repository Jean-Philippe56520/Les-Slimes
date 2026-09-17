from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass

from ..runtime.actors import RuntimeActor
from ..runtime.storage import RuntimeStorage

AUTH_TOKEN_HASHES_ENV = "LES_SLIMES_AUTH_TOKEN_HASHES_JSON"
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class AuthConfigurationError(RuntimeError):
    """Raised when the API authentication configuration is missing or invalid."""


def hash_token(token: str) -> str:
    if not token:
        raise ValueError("Authentication token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ActorAuthenticator:
    """Resolve bearer credentials to persistent runtime actors.

    The client never selects its own actor id. The actor is derived exclusively from
    a server-side mapping of actor ids to SHA-256 token digests.
    """

    storage: RuntimeStorage
    token_hashes: dict[str, str]

    def __post_init__(self) -> None:
        normalized: dict[str, str] = {}
        seen_hashes: set[str] = set()
        for actor_id, digest in self.token_hashes.items():
            actor_id = str(actor_id).strip()
            digest = str(digest).strip().lower()
            if not actor_id:
                raise AuthConfigurationError("Authentication actor id must not be empty")
            self.storage.get_actor(actor_id)
            if _HEX_64.fullmatch(digest) is None:
                raise AuthConfigurationError(
                    f"Authentication hash for {actor_id!r} must be a SHA-256 hex digest"
                )
            if digest in seen_hashes:
                raise AuthConfigurationError("Authentication token hashes must be unique")
            seen_hashes.add(digest)
            normalized[actor_id] = digest
        object.__setattr__(self, "token_hashes", normalized)

    @classmethod
    def from_env(cls, storage: RuntimeStorage) -> "ActorAuthenticator":
        raw = os.getenv(AUTH_TOKEN_HASHES_ENV, "").strip()
        if not raw:
            return cls(storage, {})
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AuthConfigurationError(
                f"{AUTH_TOKEN_HASHES_ENV} must contain valid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise AuthConfigurationError(
                f"{AUTH_TOKEN_HASHES_ENV} must be a JSON object mapping actor ids to hashes"
            )
        return cls(storage, {str(key): str(value) for key, value in parsed.items()})

    @property
    def configured(self) -> bool:
        return bool(self.token_hashes)

    def authenticate(self, token: str) -> RuntimeActor:
        if not self.configured:
            raise AuthConfigurationError(
                f"Authentication is not configured; set {AUTH_TOKEN_HASHES_ENV}"
            )
        candidate = hash_token(token)
        matched_actor_id: str | None = None
        for actor_id, configured_hash in self.token_hashes.items():
            if hmac.compare_digest(candidate, configured_hash):
                matched_actor_id = actor_id
        if matched_actor_id is None:
            raise PermissionError("Invalid authentication credentials")
        actor = self.storage.get_actor(matched_actor_id)
        if not actor.active:
            raise PermissionError("Actor is inactive")
        return actor
