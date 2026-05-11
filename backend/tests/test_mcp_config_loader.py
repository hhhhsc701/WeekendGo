from pathlib import Path

import pytest

from app.mcp.config_loader import load_mcp_config
from app.mcp.errors import MCPConfigurationError


def test_missing_server_env_disables_only_that_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AMAP_API_KEY", "test-amap")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    config = load_mcp_config(Path("config/mcp_config.yaml"))

    assert config.servers["amap"].enabled is True
    assert config.servers["google-maps"].enabled is False
    assert "GOOGLE_MAPS_API_KEY" in (config.servers["google-maps"].unavailable_reason or "")


def test_strict_env_still_raises_for_explicit_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    with pytest.raises(MCPConfigurationError, match="GOOGLE_MAPS_API_KEY"):
        load_mcp_config(Path("config/mcp_config.yaml"), enabled_servers={"google-maps"}, strict_env=True)
