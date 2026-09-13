from pathlib import Path

from les_slimes.config import WorldConfig


def test_default_yaml_matches_python_defaults():
    root = Path(__file__).resolve().parents[1]
    yaml_config = WorldConfig.from_yaml(root / "config" / "default.yaml")
    assert yaml_config == WorldConfig()
