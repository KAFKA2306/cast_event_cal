# MCP runtime configuration

`cast-event-cal-mcp` remains local-only by default and reads its runtime binding from environment variables.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CAST_EVENT_MCP_HOST` | `127.0.0.1` | HTTP/SSE bind host. Use `0.0.0.0` only when the surrounding runtime/network policy is intended to expose the service. |
| `CAST_EVENT_MCP_PORT` | `8011` | TCP port, validated in the range 1–65535. |
| `CAST_EVENT_MCP_TRANSPORT` | `streamable-http` | One of `streamable-http`, `sse`, or `stdio`. |

Container example:

```bash
CAST_EVENT_MCP_HOST=0.0.0.0 CAST_EVENT_MCP_PORT=8011 cast-event-cal-mcp
```

For stdio clients, set `CAST_EVENT_MCP_TRANSPORT=stdio`; host and port are then not passed to the MCP server.

These settings change only server transport/binding. The MCP tools continue to read the canonical snapshot through `mcp_read_model` and do not introduce a second data or classification path.
