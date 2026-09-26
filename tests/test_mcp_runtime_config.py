from __future__ import annotations

import pytest

from cast_event_cal import mcp_server


_ENV_KEYS = ("CAST_EVENT_MCP_HOST", "CAST_EVENT_MCP_PORT", "CAST_EVENT_MCP_TRANSPORT")


def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_runtime_config_preserves_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_env(monkeypatch)
    assert mcp_server._runtime_config() == ("127.0.0.1", 8011, "streamable-http")


def test_runtime_config_accepts_container_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAST_EVENT_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("CAST_EVENT_MCP_PORT", "18011")
    monkeypatch.setenv("CAST_EVENT_MCP_TRANSPORT", "SSE")
    assert mcp_server._runtime_config() == ("0.0.0.0", 18011, "sse")


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port"])
def test_runtime_config_rejects_invalid_port(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("CAST_EVENT_MCP_PORT", port)
    with pytest.raises(ValueError, match="CAST_EVENT_MCP_PORT"):
        mcp_server._runtime_config()


def test_main_passes_network_binding_to_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAST_EVENT_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("CAST_EVENT_MCP_PORT", "18011")
    monkeypatch.setenv("CAST_EVENT_MCP_TRANSPORT", "streamable-http")
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    mcp_server.main()

    assert calls == [(("streamable-http",), {"host": "0.0.0.0", "port": 18011})]


def test_main_uses_stdio_without_network_options(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("CAST_EVENT_MCP_TRANSPORT", "stdio")
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    mcp_server.main()

    assert calls == [(("stdio",), {})]
