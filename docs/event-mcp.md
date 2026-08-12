# Event MCP

`cast_event_cal` is the canonical repository for VRChat event ingestion, normalization, deterministic classification, ontology matching, and provenance. `KAFKA2306/vrc_cast_event_calender` is a projection/deployment repository only.

## Runtime

Install the MCP extra and run the localhost read-only server:

```bash
pip install -e '.[mcp]'
cast-event-cal-mcp
```

The server binds to `127.0.0.1:8011` using the MCP Python SDK v2 `MCPServer` implementation and Streamable HTTP. The implementation does not depend on the legacy MCP handshake/session model.

## Read-only tools

- `search_events`
- `get_event`
- `get_tonight_events`
- `get_series`
- `get_source_health`
- `get_classification_audit`
- `get_ontology`
- `get_data_quality`
- `get_methodology`

Search/list calls are bounded by `limit <= 100` and use `offset` pagination. `get_tonight_events(date_jst=...)` accepts an explicit JST date so historical replay does not depend on the current date.

## Canonical and provenance contract

MCP reads the existing canonical `public/*.json` artifacts; it does not reimplement acquisition or classification. Event responses preserve the canonical event record and add a `provenance` object containing the available canonical ID, schema version, event start, source-created/first-seen/last-seen/snapshot-generated timestamps, source type/ID/URL, classification rule/reason, ontology ID, freshness age, and explicit null reasons for tracked fields not recorded in the public event.

Missing facts are not inferred. The event-series ontology remains human-curated, ambiguous ontology matches are rejected, and the deterministic classifier remains the canonical daily classifier.

## Publication boundary

The deployment repository writes `projection-manifest.json` with the canonical source repository and commit plus SHA-256/byte metadata for deployed artifacts. Its verification gate checks the live projection against that manifest. Classification logic is not canonical in the deployment repository.

## Verification

```bash
pip install -e '.[dev]'
pytest tests/test_mcp_contract.py tests/test_mcp_acceptance.py
```

The tests cover tool discovery, public/MCP record parity, provenance fields, deterministic JST replay, ontology ambiguity fail-close behavior, bounded pagination, and the canonical/deployment boundary.
