from les_slimes.cli import build_parser
from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.governance.council import DivineCouncilStorage
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=55,
                width=20.0,
                height=20.0,
                initial_slimes=2,
                initial_food=2,
                max_food=10,
                food_spawn_probability=0.0,
            )
        )
    )
    return repo


def test_governance_cli_commands_are_registered():
    parser = build_parser()
    args = parser.parse_args(["governance-status", "--actor", "order"])
    assert args.command == "governance-status"
    assert args.actor == "order"

    args = parser.parse_args(
        [
            "governance-budget",
            "--actor",
            "chaos",
            "--kind",
            "miracle",
            "--delta",
            "3",
            "--reason",
            "test",
        ]
    )
    assert args.command == "governance-budget"
    assert args.delta == 3


def test_divine_council_persists_real_positions(tmp_path):
    repo = build_repo(tmp_path)
    councils = DivineCouncilStorage(repo)
    council_id = councils.create_council("2026-W38", "Conseil hebdomadaire")
    councils.set_position(
        council_id,
        "order",
        position="support",
        argument="Stabilise une structure durable.",
        proposal_id=12,
    )
    councils.set_position(
        council_id,
        "chaos",
        position="amend",
        argument="Préserver davantage de diversité.",
        proposal_id=12,
    )

    positions = councils.list_positions(council_id)
    assert [item["actor_id"] for item in positions] == ["chaos", "order"]
    assert {item["position"] for item in positions} == {"support", "amend"}
