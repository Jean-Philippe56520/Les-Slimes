from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Callable, Iterable, Protocol, runtime_checkable

from ..world.engine import World


@runtime_checkable
class RelationalRepository(Protocol):
    """Backend contract shared by the canonical runtime and governance layers.

    The contract deliberately exposes only the database primitives required by the
    existing storage services. SQLite remains the only implementation in this PR;
    PostgreSQL can implement the same semantics without changing the World Worker.
    """

    backend_name: str

    def _connect(self) -> AbstractContextManager[Any]: ...

    def storage_exists(self) -> bool: ...

    def initialize_schema(self) -> None: ...

    def exists(self) -> bool: ...

    def table_exists(self, conn: Any, table_name: str) -> bool: ...

    def column_names(self, conn: Any, table_name: str) -> set[str]: ...

    def execute_script(self, conn: Any, script: str) -> None: ...

    def begin_write(self, conn: Any) -> None: ...

    def lock_writer_lease(self, conn: Any, lease_name: str) -> None: ...

    def install_governance_guards(self, conn: Any) -> None: ...

    def _set_meta(self, conn: Any, key: str, value: bytes) -> None: ...

    def save_world(
        self,
        world: World,
        *,
        transaction_guard: Callable[[Any], None] | None = None,
        transaction_mutator: Callable[[Any], None] | None = None,
    ) -> None: ...

    def load_world(self) -> World: ...

    def add_observer_proposal(
        self,
        tick: int,
        proposal: dict,
        *,
        status: str = "pending",
    ) -> int: ...

    def get_observer_proposal(self, proposal_id: int) -> Any: ...

    def list_observer_proposals(
        self,
        *,
        status: str | None = None,
        limit: int = 200,
    ) -> list[Any]: ...

    def update_observer_proposal(
        self,
        proposal_id: int,
        *,
        status: str,
        result: dict | None = None,
    ) -> None: ...

    def checkpoints(self, limit: int = 500) -> list[Any]: ...

    def recent_events(self, limit: int = 200) -> list[Any]: ...
