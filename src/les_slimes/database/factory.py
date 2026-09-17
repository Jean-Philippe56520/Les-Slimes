from __future__ import annotations

import os
from pathlib import Path

from .base import RelationalRepository
from .postgres_repo import PostgreSQLRepository
from .sqlite_repo import SQLiteRepository

DATABASE_URL_ENV = "LES_SLIMES_DATABASE_URL"
DATABASE_PATH_ENV = "LES_SLIMES_DB_PATH"


def repository_from_target(target: str | Path) -> RelationalRepository:
    value = str(target)
    if value.startswith(("postgresql://", "postgres://")):
        return PostgreSQLRepository(value)
    return SQLiteRepository(value)


def canonical_repository_from_env() -> RelationalRepository:
    database_url = os.getenv(DATABASE_URL_ENV, "").strip()
    if database_url:
        return repository_from_target(database_url)
    return SQLiteRepository(os.getenv(DATABASE_PATH_ENV, "data/world.sqlite"))
