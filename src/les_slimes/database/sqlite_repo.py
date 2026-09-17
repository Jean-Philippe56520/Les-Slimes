from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

from ..biology.genetics import Genome
from ..cognition.memory import FoodMemory
from ..cognition.rules import BehaviorRule
from ..config import WorldConfig
from ..entities import Food, HeardSignal, Relation, Slime
from ..world.engine import World
from ..world.mysteries import MysteryObject


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS slimes (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    generation INTEGER NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    heading REAL NOT NULL,
    energy REAL NOT NULL,
    health REAL NOT NULL,
    age_ticks INTEGER NOT NULL,
    born_tick INTEGER NOT NULL,
    last_reproduction_tick INTEGER NOT NULL,
    genome_json TEXT NOT NULL,
    distance_travelled REAL NOT NULL,
    food_eaten INTEGER NOT NULL,
    offspring_count INTEGER NOT NULL,
    current_action TEXT NOT NULL,
    alive INTEGER NOT NULL,
    last_signal_emit_tick INTEGER NOT NULL DEFAULT -1000000
);

CREATE TABLE IF NOT EXISTS memories (
    slime_id TEXT NOT NULL,
    memory_index INTEGER NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    strength REAL NOT NULL,
    last_seen_tick INTEGER NOT NULL,
    PRIMARY KEY (slime_id, memory_index),
    FOREIGN KEY (slime_id) REFERENCES slimes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relations (
    slime_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    familiarity REAL NOT NULL,
    trust REAL NOT NULL,
    interactions INTEGER NOT NULL,
    last_interaction_tick INTEGER NOT NULL,
    PRIMARY KEY (slime_id, target_id),
    FOREIGN KEY (slime_id) REFERENCES slimes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES slimes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS signal_associations (
    slime_id TEXT NOT NULL,
    signal TEXT NOT NULL,
    food_strength REAL NOT NULL,
    PRIMARY KEY (slime_id, signal),
    FOREIGN KEY (slime_id) REFERENCES slimes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS heard_signals (
    slime_id TEXT NOT NULL,
    heard_index INTEGER NOT NULL,
    signal TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    tick INTEGER NOT NULL,
    source_id TEXT,
    PRIMARY KEY (slime_id, heard_index),
    FOREIGN KEY (slime_id) REFERENCES slimes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mysteries (
    id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_rules (
    id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY,
    x REAL NOT NULL,
    y REAL NOT NULL,
    nutrition REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY,
    tick INTEGER NOT NULL,
    type TEXT NOT NULL,
    subject_id TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_tick ON events(tick);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_subject ON events(subject_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_signal_associations_signal ON signal_associations(signal);

CREATE TABLE IF NOT EXISTS observer_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    proposal_json TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_observer_proposals_status
ON observer_proposals(status);

CREATE TABLE IF NOT EXISTS checkpoints (
    tick INTEGER PRIMARY KEY,
    population INTEGER NOT NULL,
    food_count INTEGER NOT NULL,
    births INTEGER NOT NULL,
    deaths INTEGER NOT NULL,
    mean_energy REAL NOT NULL,
    mean_health REAL NOT NULL,
    max_generation INTEGER NOT NULL,
    state_digest TEXT NOT NULL
);
"""


class SQLiteRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(slimes)")
            }
            if "last_signal_emit_tick" not in columns:
                conn.execute(
                    "ALTER TABLE slimes ADD COLUMN last_signal_emit_tick "
                    "INTEGER NOT NULL DEFAULT -1000000"
                )

    def exists(self) -> bool:
        if not self.path.exists():
            return False
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'"
                ).fetchone()
                if row is None:
                    return False
                return (
                    conn.execute("SELECT 1 FROM metadata WHERE key='tick'").fetchone()
                    is not None
                )
        except sqlite3.DatabaseError:
            return False

    @staticmethod
    def _set_meta(conn: sqlite3.Connection, key: str, value: bytes) -> None:
        conn.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, sqlite3.Binary(value)),
        )

    @staticmethod
    def _int_bytes(value: int) -> bytes:
        return str(value).encode("ascii")

    def save_world(
        self,
        world: World,
        *,
        transaction_guard: Callable[[sqlite3.Connection], None] | None = None,
        transaction_mutator: Callable[[sqlite3.Connection], None] | None = None,
    ) -> None:
        self.initialize_schema()
        cfg_json = json.dumps(world.config.to_dict(), sort_keys=True).encode("utf-8")
        metrics = world.metrics()
        digest = world.state_digest()

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if transaction_guard is not None:
                transaction_guard(conn)

            self._set_meta(conn, "config", cfg_json)
            conn.execute("DELETE FROM metadata WHERE key='mode'")
            self._set_meta(conn, "tick", self._int_bytes(world.tick))
            self._set_meta(
                conn, "next_slime_number", self._int_bytes(world.next_slime_number)
            )
            self._set_meta(conn, "next_food_id", self._int_bytes(world.next_food_id))
            self._set_meta(
                conn, "next_rule_number", self._int_bytes(world.next_rule_number)
            )
            self._set_meta(
                conn, "next_mystery_number", self._int_bytes(world.next_mystery_number)
            )
            self._set_meta(
                conn, "event_sequence", self._int_bytes(world.event_sequence)
            )
            self._set_meta(conn, "births_total", self._int_bytes(world.births_total))
            self._set_meta(conn, "deaths_total", self._int_bytes(world.deaths_total))
            self._set_meta(conn, "rng_state", world.rng_state_bytes())

            conn.execute("DELETE FROM mysteries")
            conn.execute("DELETE FROM behavior_rules")
            conn.execute("DELETE FROM heard_signals")
            conn.execute("DELETE FROM signal_associations")
            conn.execute("DELETE FROM relations")
            conn.execute("DELETE FROM memories")
            conn.execute("DELETE FROM slimes")
            conn.execute("DELETE FROM foods")

            conn.executemany(
                """
                INSERT INTO slimes(
                    id, parent_id, generation, x, y, heading, energy, health,
                    age_ticks, born_tick, last_reproduction_tick, genome_json,
                    distance_travelled, food_eaten, offspring_count,
                    current_action, alive, last_signal_emit_tick
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        slime.id,
                        slime.parent_id,
                        slime.generation,
                        slime.x,
                        slime.y,
                        slime.heading,
                        slime.energy,
                        slime.health,
                        slime.age_ticks,
                        slime.born_tick,
                        slime.last_reproduction_tick,
                        json.dumps(slime.genome.to_dict(), sort_keys=True),
                        slime.distance_travelled,
                        slime.food_eaten,
                        slime.offspring_count,
                        slime.current_action,
                        int(slime.alive),
                        slime.last_signal_emit_tick,
                    )
                    for slime in world.slimes.values()
                ],
            )

            memory_rows = []
            relation_rows = []
            association_rows = []
            heard_rows = []
            for slime in world.slimes.values():
                for idx, memory in enumerate(slime.memories):
                    memory_rows.append(
                        (
                            slime.id,
                            idx,
                            memory.x,
                            memory.y,
                            memory.strength,
                            memory.last_seen_tick,
                        )
                    )
                for target_id, relation in slime.relations.items():
                    if target_id not in world.slimes:
                        continue
                    relation_rows.append(
                        (
                            slime.id,
                            target_id,
                            relation.familiarity,
                            relation.trust,
                            relation.interactions,
                            relation.last_interaction_tick,
                        )
                    )
                for signal, strength in slime.signal_food_associations.items():
                    association_rows.append((slime.id, signal, strength))
                for idx, heard in enumerate(slime.heard_signals):
                    heard_rows.append(
                        (
                            slime.id,
                            idx,
                            heard.signal,
                            heard.x,
                            heard.y,
                            heard.tick,
                            heard.source_id,
                        )
                    )

            conn.executemany(
                """
                INSERT INTO memories(slime_id, memory_index, x, y, strength, last_seen_tick)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                memory_rows,
            )
            conn.executemany(
                """
                INSERT INTO relations(
                    slime_id, target_id, familiarity, trust,
                    interactions, last_interaction_tick
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                relation_rows,
            )
            conn.executemany(
                """
                INSERT INTO signal_associations(slime_id, signal, food_strength)
                VALUES (?, ?, ?)
                """,
                association_rows,
            )
            conn.executemany(
                """
                INSERT INTO heard_signals(
                    slime_id, heard_index, signal, x, y, tick, source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                heard_rows,
            )

            conn.executemany(
                "INSERT INTO mysteries(id, payload_json) VALUES (?, ?)",
                [
                    (
                        mystery.id,
                        json.dumps(mystery.to_dict(include_hidden=True), sort_keys=True),
                    )
                    for mystery in world.mysteries.values()
                ],
            )

            conn.executemany(
                "INSERT INTO behavior_rules(id, payload_json) VALUES (?, ?)",
                [
                    (rule.id, json.dumps(rule.to_dict(), sort_keys=True))
                    for rule in world.behavior_rules.values()
                ],
            )

            conn.executemany(
                "INSERT INTO foods(id, x, y, nutrition) VALUES (?, ?, ?, ?)",
                [(f.id, f.x, f.y, f.nutrition) for f in world.foods.values()],
            )

            conn.executemany(
                """
                INSERT OR IGNORE INTO events(sequence, tick, type, subject_id, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.sequence,
                        event.tick,
                        event.type,
                        event.subject_id,
                        json.dumps(event.payload, sort_keys=True),
                    )
                    for event in world.pending_events
                ],
            )

            conn.execute(
                """
                INSERT INTO checkpoints(
                    tick, population, food_count, births, deaths,
                    mean_energy, mean_health, max_generation, state_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tick) DO UPDATE SET
                    population=excluded.population,
                    food_count=excluded.food_count,
                    births=excluded.births,
                    deaths=excluded.deaths,
                    mean_energy=excluded.mean_energy,
                    mean_health=excluded.mean_health,
                    max_generation=excluded.max_generation,
                    state_digest=excluded.state_digest
                """,
                (
                    metrics.tick,
                    metrics.population,
                    metrics.food_count,
                    metrics.births,
                    metrics.deaths,
                    metrics.mean_energy,
                    metrics.mean_health,
                    metrics.max_generation,
                    digest,
                ),
            )
            if transaction_mutator is not None:
                transaction_mutator(conn)
            conn.commit()

        world.pending_events.clear()

    def load_world(self) -> World:
        if not self.exists():
            raise FileNotFoundError(f"No saved world found at {self.path}")
        self.initialize_schema()

        with self._connect() as conn:
            meta = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value FROM metadata")
            }
            config_raw = meta["config"]
            if isinstance(config_raw, bytes):
                config_raw = config_raw.decode("utf-8")
            config = WorldConfig.from_dict(json.loads(config_raw))
            world = World(config, initialize=False)

            world.tick = int(bytes(meta["tick"]).decode("ascii"))
            world.next_slime_number = int(
                bytes(meta["next_slime_number"]).decode("ascii")
            )
            world.next_food_id = int(bytes(meta["next_food_id"]).decode("ascii"))
            world.next_rule_number = int(
                bytes(meta.get("next_rule_number", b"1")).decode("ascii")
            )
            world.next_mystery_number = int(
                bytes(meta.get("next_mystery_number", b"1")).decode("ascii")
            )
            world.event_sequence = int(
                bytes(meta["event_sequence"]).decode("ascii")
            )
            world.births_total = int(bytes(meta["births_total"]).decode("ascii"))
            world.deaths_total = int(bytes(meta["deaths_total"]).decode("ascii"))
            world.restore_rng_state(bytes(meta["rng_state"]))

            memories_by_slime: dict[str, list[FoodMemory]] = {}
            for row in conn.execute(
                "SELECT * FROM memories ORDER BY slime_id, memory_index"
            ):
                memories_by_slime.setdefault(row["slime_id"], []).append(
                    FoodMemory(
                        x=row["x"],
                        y=row["y"],
                        strength=row["strength"],
                        last_seen_tick=row["last_seen_tick"],
                    )
                )

            relations_by_slime: dict[str, dict[str, Relation]] = {}
            for row in conn.execute("SELECT * FROM relations ORDER BY slime_id, target_id"):
                relations_by_slime.setdefault(row["slime_id"], {})[row["target_id"]] = Relation(
                    familiarity=row["familiarity"],
                    trust=row["trust"],
                    interactions=row["interactions"],
                    last_interaction_tick=row["last_interaction_tick"],
                )

            associations_by_slime: dict[str, dict[str, float]] = {}
            for row in conn.execute(
                "SELECT * FROM signal_associations ORDER BY slime_id, signal"
            ):
                associations_by_slime.setdefault(row["slime_id"], {})[
                    row["signal"]
                ] = row["food_strength"]

            heard_by_slime: dict[str, list[HeardSignal]] = {}
            for row in conn.execute(
                "SELECT * FROM heard_signals ORDER BY slime_id, heard_index"
            ):
                heard_by_slime.setdefault(row["slime_id"], []).append(
                    HeardSignal(
                        signal=row["signal"],
                        x=row["x"],
                        y=row["y"],
                        tick=row["tick"],
                        source_id=row["source_id"],
                    )
                )

            for row in conn.execute("SELECT * FROM mysteries ORDER BY id"):
                mystery = MysteryObject.from_dict(json.loads(row["payload_json"]))
                world.mysteries[mystery.id] = mystery

            for row in conn.execute("SELECT * FROM behavior_rules ORDER BY id"):
                rule = BehaviorRule.from_dict(json.loads(row["payload_json"]))
                world.behavior_rules[rule.id] = rule

            for row in conn.execute("SELECT * FROM slimes ORDER BY id"):
                slime = Slime(
                    id=row["id"],
                    parent_id=row["parent_id"],
                    generation=row["generation"],
                    x=row["x"],
                    y=row["y"],
                    heading=row["heading"],
                    energy=row["energy"],
                    health=row["health"],
                    age_ticks=row["age_ticks"],
                    born_tick=row["born_tick"],
                    last_reproduction_tick=row["last_reproduction_tick"],
                    genome=Genome.from_dict(json.loads(row["genome_json"])),
                    memories=memories_by_slime.get(row["id"], []),
                    relations=relations_by_slime.get(row["id"], {}),
                    signal_food_associations=associations_by_slime.get(row["id"], {}),
                    heard_signals=heard_by_slime.get(row["id"], []),
                    last_signal_emit_tick=row["last_signal_emit_tick"],
                    distance_travelled=row["distance_travelled"],
                    food_eaten=row["food_eaten"],
                    offspring_count=row["offspring_count"],
                    current_action=row["current_action"],
                    alive=bool(row["alive"]),
                )
                world.slimes[slime.id] = slime

            world.replace_foods(
                Food(
                    id=row["id"],
                    x=row["x"],
                    y=row["y"],
                    nutrition=row["nutrition"],
                )
                for row in conn.execute("SELECT * FROM foods ORDER BY id")
            )
            world.pending_events = []
            return world

    def add_observer_proposal(
        self, tick: int, proposal: dict, *, status: str = "pending"
    ) -> int:
        self.initialize_schema()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO observer_proposals(tick, proposal_json, status) "
                "VALUES (?, ?, ?)",
                (tick, json.dumps(proposal, sort_keys=True), status),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_observer_proposal(self, proposal_id: int) -> sqlite3.Row:
        self.initialize_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM observer_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            return row

    def list_observer_proposals(
        self, *, status: str | None = None, limit: int = 200
    ) -> list[sqlite3.Row]:
        self.initialize_schema()
        with self._connect() as conn:
            if status is None:
                return conn.execute(
                    "SELECT * FROM observer_proposals ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM observer_proposals WHERE status=? "
                "ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()

    def update_observer_proposal(
        self, proposal_id: int, *, status: str, result: dict | None = None
    ) -> None:
        self.initialize_schema()
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE observer_proposals SET status=?, result_json=? WHERE id=?",
                (
                    status,
                    json.dumps(result, sort_keys=True) if result is not None else None,
                    proposal_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(proposal_id)
            conn.commit()

    def checkpoints(self, limit: int = 500) -> list[sqlite3.Row]:
        self.initialize_schema()
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM checkpoints ORDER BY tick DESC LIMIT ?", (limit,)
            ).fetchall()

    def recent_events(self, limit: int = 200) -> list[sqlite3.Row]:
        self.initialize_schema()
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM events ORDER BY sequence DESC LIMIT ?", (limit,)
            ).fetchall()
