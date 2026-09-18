from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Mapping
from datetime import UTC, datetime

from ..database.base import RelationalRepository
from ..governance.storage import GovernanceStorage
from ..runtime.storage import RuntimeStorage


SESSION_META_KEY = "openai/session"
SUBJECT_META_KEY = "openai/subject"


@dataclass(frozen=True, slots=True)
class DivineRequestMetadata:
    session_id: str
    subject_id: str

    @classmethod
    def from_meta(cls, meta: Mapping[str, Any]) -> "DivineRequestMetadata":
        session = meta.get(SESSION_META_KEY)
        subject = meta.get(SUBJECT_META_KEY)
        if not isinstance(session, str) or not session.strip():
            raise PermissionError("DIVINE_SESSION_METADATA_MISSING")
        if not isinstance(subject, str) or not subject.strip():
            raise PermissionError("DIVINE_SUBJECT_METADATA_MISSING")
        return cls(session_id=session.strip(), subject_id=subject.strip())

def _hash_identifier(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("identifier must not be empty")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DivineSessionBinding:
    session_hash: str
    subject_hash: str
    actor_id: str
    status: str
    created_at_utc: datetime
    created_by: str
    last_seen_at_utc: datetime
    revoked_at_utc: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None

    @property
    def active(self) -> bool:
        return self.status == "active" and self.revoked_at_utc is None


class DivineSessionBindingService:
    """Persisted fail-closed mapping from ChatGPT conversation metadata to Les Slimes actors."""

    ALLOWED_ACTORS = frozenset({"father", "herald", "order", "chaos"})

    def __init__(self, repository: RelationalRepository) -> None:
        self.repository = repository
        self.runtime = RuntimeStorage(repository)
        self.governance = GovernanceStorage(repository)

    @staticmethod
    def _now(now_utc: datetime | None = None) -> datetime:
        now = now_utc or datetime.now(UTC)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("timestamps must be timezone-aware")
        return now.astimezone(UTC)

    @staticmethod
    def _require_father(performed_by: str) -> None:
        if performed_by != "father":
            raise PermissionError("Only the Father may bind or revoke divine sessions")

    def bind(
        self,
        *,
        session_id: str,
        subject_id: str,
        actor_id: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ) -> DivineSessionBinding:
        self._require_father(performed_by)
        if actor_id not in self.ALLOWED_ACTORS:
            raise ValueError("Session bindings are limited to father, herald, order and chaos")
        actor = self.runtime.get_actor(actor_id)
        if not actor.active:
            raise PermissionError("Cannot bind an inactive actor")

        session_hash = _hash_identifier(session_id)
        subject_hash = _hash_identifier(subject_id)
        now = self._now(now_utc)
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            existing = conn.execute(
                "SELECT * FROM divine_session_bindings WHERE session_hash = ?",
                (session_hash,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["status"]) == "active"
                    and hmac.compare_digest(str(existing["subject_hash"]), subject_hash)
                    and str(existing["actor_id"]) == actor_id
                ):
                    conn.execute(
                        "UPDATE divine_session_bindings SET last_seen_at_utc = ? WHERE session_hash = ?",
                        (now.isoformat(), session_hash),
                    )
                    conn.commit()
                    return self.get_by_hash(session_hash)
                raise PermissionError("Session is already bound and must be revoked before rebinding")

            conn.execute(
                """
                INSERT INTO divine_session_bindings(
                    session_hash, subject_hash, actor_id, status,
                    created_at_utc, created_by, last_seen_at_utc
                ) VALUES (?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    session_hash,
                    subject_hash,
                    actor_id,
                    now.isoformat(),
                    performed_by,
                    now.isoformat(),
                ),
            )
            self.governance.append_audit_in_transaction(
                conn,
                event_type="divine_session_bound",
                actor_id=performed_by,
                subject_actor_id=actor_id,
                payload={
                    "session_hash": session_hash,
                    "subject_hash": subject_hash,
                },
                created_at_utc=now,
            )
            conn.commit()
        return self.get_by_hash(session_hash)

    def revoke(
        self,
        *,
        session_id: str,
        reason: str,
        performed_by: str = "father",
        now_utc: datetime | None = None,
    ) -> DivineSessionBinding:
        self._require_father(performed_by)
        reason = reason.strip()
        if not reason:
            raise ValueError("revocation reason is required")
        session_hash = _hash_identifier(session_id)
        now = self._now(now_utc)
        with self.repository._connect() as conn:
            self.repository.begin_write(conn)
            row = conn.execute(
                "SELECT actor_id, status FROM divine_session_bindings WHERE session_hash = ?",
                (session_hash,),
            ).fetchone()
            if row is None:
                raise KeyError(session_hash)
            if str(row["status"]) != "active":
                raise PermissionError("Session is already revoked")
            actor_id = str(row["actor_id"])
            conn.execute(
                """
                UPDATE divine_session_bindings
                SET status='revoked', revoked_at_utc=?, revoked_by=?, revoke_reason=?
                WHERE session_hash=?
                """,
                (now.isoformat(), performed_by, reason, session_hash),
            )
            self.governance.append_audit_in_transaction(
                conn,
                event_type="divine_session_revoked",
                actor_id=performed_by,
                subject_actor_id=actor_id,
                payload={"session_hash": session_hash, "reason": reason},
                created_at_utc=now,
            )
            conn.commit()
        return self.get_by_hash(session_hash)

    def resolve(
        self,
        *,
        session_id: str,
        subject_id: str,
        now_utc: datetime | None = None,
    ) -> DivineSessionBinding:
        session_hash = _hash_identifier(session_id)
        subject_hash = _hash_identifier(subject_id)
        now = self._now(now_utc)
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_session_bindings WHERE session_hash = ?",
                (session_hash,),
            ).fetchone()
            if row is None:
                raise PermissionError("DIVINE_SESSION_UNBOUND")
            if str(row["status"]) != "active" or row["revoked_at_utc"] is not None:
                raise PermissionError("DIVINE_SESSION_REVOKED")
            if not hmac.compare_digest(str(row["subject_hash"]), subject_hash):
                raise PermissionError("DIVINE_SESSION_SUBJECT_MISMATCH")
            actor = self.runtime.get_actor(str(row["actor_id"]))
            if not actor.active:
                raise PermissionError("DIVINE_SESSION_ACTOR_INACTIVE")
            conn.execute(
                "UPDATE divine_session_bindings SET last_seen_at_utc = ? WHERE session_hash = ?",
                (now.isoformat(), session_hash),
            )
            conn.commit()
        return self.get_by_hash(session_hash)

    def get_by_hash(self, session_hash: str) -> DivineSessionBinding:
        with self.repository._connect() as conn:
            row = conn.execute(
                "SELECT * FROM divine_session_bindings WHERE session_hash = ?",
                (session_hash,),
            ).fetchone()
        if row is None:
            raise KeyError(session_hash)
        return DivineSessionBinding(
            session_hash=str(row["session_hash"]),
            subject_hash=str(row["subject_hash"]),
            actor_id=str(row["actor_id"]),
            status=str(row["status"]),
            created_at_utc=datetime.fromisoformat(str(row["created_at_utc"])).astimezone(UTC),
            created_by=str(row["created_by"]),
            last_seen_at_utc=datetime.fromisoformat(str(row["last_seen_at_utc"])).astimezone(UTC),
            revoked_at_utc=(
                datetime.fromisoformat(str(row["revoked_at_utc"])).astimezone(UTC)
                if row["revoked_at_utc"] is not None
                else None
            ),
            revoked_by=str(row["revoked_by"]) if row["revoked_by"] is not None else None,
            revoke_reason=(
                str(row["revoke_reason"]) if row["revoke_reason"] is not None else None
            ),
        )
