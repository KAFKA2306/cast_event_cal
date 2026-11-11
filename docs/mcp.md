# Event MCP

MCP is a read-only adapter to the canonical `public/*.json` outputs. It must not reimplement acquisition, classification, identity, or ontology.

```bash
pip install -e '.[mcp]'
cast-event-cal-mcp
```

Default: Streamable HTTP at `127.0.0.1:8011`. Environment: `CAST_EVENT_MCP_HOST` (default `127.0.0.1`), `CAST_EVENT_MCP_PORT` (default `8011`), `CAST_EVENT_MCP_TRANSPORT` (`streamable-http`, `sse`, or `stdio`). Expose a non-loopback address only with appropriate network controls.

Tools: `search_events`, `get_event`, `get_tonight_events`, `get_series`, `get_source_health`, `get_classification_audit`, `get_ontology`, `get_data_quality`, `get_methodology`. Search/list are paginated (`limit <= 100`, `offset`). `get_tonight_events(date_jst=...)` supports deterministic replay.

Preserve canonical records and available provenance (source/time/decision/ontology). Missing values remain null with reasons, not fabricated. Ambiguous ontology matches and duplicate event IDs fail closed. The deployment repo is projection-only.

Verification: `pytest -q tests/test_mcp_contract.py tests/test_mcp_acceptance.py tests/test_mcp_runtime_config.py`.
