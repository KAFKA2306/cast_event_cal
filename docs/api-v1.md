# Event API v1

`scripts/build_public_api.py` generates these distributions from `public/events.json`:

- `public/api/v1/events.json`: complete versioned event feed
- `public/api/v1/events.csv`: key columns for tabular clients
- `public/api/v1/facets.json`: category/status/source/mode counts
- `public/api/v1/manifest.json`: count, source hash, artifact hashes and sizes

Use `manifest.json` hashes for cache validation. CSV omits detailed provenance; use JSON when source and classification evidence are needed. Missing source facts are never filled in.

```bash
python scripts/build_public_api.py
python scripts/audit_public_feed.py public/api/v1/events.json --report build/api-audit.json
```

Public paths are relative to the active deployment root; do not hard-code the legacy `vrc_cast_event_calender` GitHub Pages path.
