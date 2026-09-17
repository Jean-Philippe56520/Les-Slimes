from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_external_surfaces_cannot_bypass_governance_admin_service():
    guarded = {
        "dashboard/app.py": [
            "set_actor_permissions(",
            "set_actor_active(",
            "upsert_actor(",
            "UPDATE runtime_actors",
            "INSERT INTO divine_budget_ledger",
            "UPDATE divine_actor_state",
            "UPDATE divine_sanctions",
        ],
        "src/les_slimes/cli.py": [
            "set_actor_permissions(",
            "set_actor_active(",
            "upsert_actor(",
            "UPDATE runtime_actors",
            "INSERT INTO divine_budget_ledger",
            "UPDATE divine_actor_state",
            "UPDATE divine_sanctions",
        ],
        "src/les_slimes/observer/proposals.py": [
            "set_actor_permissions(",
            "set_actor_active(",
            "upsert_actor(",
            "UPDATE runtime_actors",
            "INSERT INTO divine_budget_ledger",
            "UPDATE divine_actor_state",
            "UPDATE divine_sanctions",
        ],
    }

    for relative_path, forbidden in guarded.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, (
                f"{relative_path} bypasses GovernanceAdminService via {token}"
            )


def test_governance_package_initializer_stays_low_level():
    text = (ROOT / "src/les_slimes/governance/__init__.py").read_text(encoding="utf-8")
    assert "from .policy import" not in text
    assert "from .service import" not in text
    assert "from .storage import" not in text
