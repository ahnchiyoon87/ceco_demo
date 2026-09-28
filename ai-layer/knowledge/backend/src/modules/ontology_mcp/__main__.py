"""Entrypoint for the read-only ontology search MCP server.

Run with:  python -m backend.src.modules.ontology_mcp
Transport is chosen by the MCP_TRANSPORT setting:
  stdio (default) | http / streamable-http | sse
"""

from __future__ import annotations

from ...shared.kernel.settings import get_settings
from .server import build_server

# Map the MCP_TRANSPORT setting onto FastMCP's transport names.
_NETWORK_TRANSPORTS = {
    "http": "streamable-http",
    "streamable-http": "streamable-http",
    "sse": "sse",
}


def serve() -> None:
    """Build the MCP server and run it over the configured transport."""

    settings = get_settings()
    mcp = build_server()

    transport = _NETWORK_TRANSPORTS.get(settings.mcp_transport)
    if transport is not None:
        # Networked transports (streamable-HTTP / legacy SSE) bind host+port.
        mcp.settings.host = settings.mcp_host
        mcp.settings.port = settings.mcp_port
        mcp.run(transport=transport)
    else:
        mcp.run(transport="stdio")


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
