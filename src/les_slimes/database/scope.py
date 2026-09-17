from __future__ import annotations

import sqlite3
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sqlite_repo import SQLiteRepository


PERSISTENCE_SCOPE_KEY = "persistence_scope"


class PersistenceScope(StrEnum):
    CANONICAL = "canonical"
    NON_CANONICAL_EXPERIMENT = "non_canonical_experiment"


class PersistenceScopeError(RuntimeError):
    pass


def _text(value: object) -> str:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def persistence_scope_from_connection(
    conn: sqlite3.Connection,
) -> PersistenceScope | None:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'"
    ).fetchone()
    if table is None:
        return None

    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?", (PERSISTENCE_SCOPE_KEY,)
    ).fetchone()
    if row is not None:
        raw = row[0]
        try:
            return PersistenceScope(_text(raw))
        except ValueError as exc:
            raise PersistenceScopeError(
                f"Unknown persistence scope {_text(raw)!r}"
            ) from exc

    # Databases created before persistence scopes existed are the historical
    # canonical database only. A database without a saved world remains unscoped.
    legacy_world = conn.execute(
        "SELECT 1 FROM metadata WHERE key = 'tick'"
    ).fetchone()
    if legacy_world is not None:
        return PersistenceScope.CANONICAL
    return None


def get_persistence_scope(repository: SQLiteRepository) -> PersistenceScope | None:
    if not repository.path.exists():
        return None
    with repository._connect() as conn:
        return persistence_scope_from_connection(conn)


def set_persistence_scope(
    repository: SQLiteRepository,
    scope: PersistenceScope,
) -> PersistenceScope:
    repository.initialize_schema()
    current = get_persistence_scope(repository)
    if current is not None and current != scope:
        raise PersistenceScopeError(
            f"Cannot change persistence scope from {current.value!r} to {scope.value!r}"
        )
    with repository._connect() as conn:
        repository._set_meta(conn, PERSISTENCE_SCOPE_KEY, scope.value.encode("utf-8"))
        conn.commit()
    return scope


def require_persistence_scope(
    repository: SQLiteRepository,
    expected: PersistenceScope,
) -> PersistenceScope:
    current = get_persistence_scope(repository)
    if current != expected:
        actual = current.value if current is not None else "unscoped"
        raise PersistenceScopeError(
            f"Persistence scope {actual!r} cannot be used as {expected.value!r}"
        )
    return current


def ensure_canonical_scope(repository: SQLiteRepository) -> PersistenceScope:
    current = get_persistence_scope(repository)
    if current != PersistenceScope.CANONICAL:
        actual = current.value if current is not None else "unscoped"
        raise PersistenceScopeError(
            f"Persistence scope {actual!r} cannot host the canonical runtime"
        )
    # Stamp legacy canonical databases explicitly once they are opened by the
    # canonical runtime. Experimental databases are rejected above.
    return set_persistence_scope(repository, PersistenceScope.CANONICAL)
