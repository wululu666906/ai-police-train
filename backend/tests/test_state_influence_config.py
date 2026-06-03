"""Tests for state influence config loading."""

from pathlib import Path

from services import state_influence_config as cfg


def test_overrides_path_points_to_backend_config():
    path = Path(cfg._OVERRIDES_PATH)
    assert path.parent.name == "config"
    assert path.name == "state_influence_overrides.json"
    assert path.parent.parent.name == "backend"
