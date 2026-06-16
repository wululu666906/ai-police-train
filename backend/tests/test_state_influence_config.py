"""Tests for state influence config loading."""

from pathlib import Path

from services import state_influence_config as cfg


def test_overrides_path_points_to_backend_config():
    path = Path(cfg._OVERRIDES_PATH)
    assert path.parent.name == "config"
    assert path.name == "state_influence_overrides.json"
    assert path.parent.parent.name == "backend"


def test_state_influence_admin_routes_are_not_registered(client):
    paths = {getattr(route, "path", "") for route in client.app.routes}

    assert "/admin/state-influence/tables" not in paths
    assert "/api/admin/state-influence/tables" not in paths
    assert not any(path.startswith("/admin/state-influence") for path in paths)
    assert not any(path.startswith("/api/admin/state-influence") for path in paths)
