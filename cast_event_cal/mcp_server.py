from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from . import mcp_read_model as read_model

MCP_SCHEMA_VERSION = "cast-event.mcp.v1"

mcp = MCPServer(
    "cast_event_cal",
    version="2.0.0",
    instructions=(
        "Read-only access to the canonical VRChat event snapshot. "
        "Preserve source timestamps, classification evidence and ontology ambiguity; "
        "do not infer missing event facts."
    ),
)


@mcp.tool()
def search_events(
    query: str | None = None,
    category: str | None = None,
    series_id: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search canonical events with deterministic filters and bounded pagination."""
    return read_model.search_events(
        query=query,
        category=category,
        series_id=series_id,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
def get_event(event_id: str) -> dict[str, Any]:
    """Get one event by canonical ID with source and classification provenance."""
    item = read_model.get_event(event_id)
    return {
        "schema_version": MCP_SCHEMA_VERSION,
        "found": item is not None,
        "event": item,
    }


@mcp.tool()
def get_tonight_events(
    date_jst: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List events whose starts_at falls on a JST calendar date; pass date_jst for replay."""
    return read_model.tonight_events(date_jst=date_jst, limit=limit, offset=offset)


@mcp.tool()
def get_series(series_id: str) -> dict[str, Any]:
    """Get one human-curated event-series ontology entry by canonical_id."""
    item = read_model.get_series(series_id)
    return {
        "schema_version": MCP_SCHEMA_VERSION,
        "found": item is not None,
        "series": item,
    }


@mcp.tool()
def get_source_health() -> dict[str, Any]:
    """Return canonical source success/failure counts and snapshot health."""
    return read_model.source_health()


@mcp.tool()
def get_classification_audit() -> dict[str, Any]:
    """Return deterministic Yahoo classifier and ontology-match audit artifacts."""
    return read_model.classification_audit()


@mcp.tool()
def get_ontology() -> dict[str, Any]:
    """Return the human-curated series ontology and fail-close matching policy."""
    return read_model.ontology()


@mcp.tool()
def get_data_quality() -> dict[str, Any]:
    """Return count parity, duplicate-ID, ambiguity and public-artifact hash checks."""
    return read_model.data_quality()


@mcp.tool()
def get_methodology() -> dict[str, Any]:
    """Return canonical/deploy boundaries, time semantics and deterministic classification policy."""
    return read_model.methodology()


def main() -> None:
    """Run the canonical Event MCP server on localhost."""
    mcp.run("streamable-http", host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
