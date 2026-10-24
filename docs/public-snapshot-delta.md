# Public snapshot delta audit

`scripts/build_public_snapshot_delta.py` compares the previous valid
`public/events.json` with the candidate snapshot by stable occurrence identity.
It is an observability projection only: it does not change event selection,
ranking, deduplication, or public UI behavior.

## Contract

The report records raw and semantic snapshot hashes, base SHA, and deterministic
`added`, `removed`, `changed`, and `unchanged` partitions.

Added occurrences use only explicit evidence:

- `new_discovery`
- `recurrence_materialized`
- `promoted_datetime_resolution`
- `other`

Removed occurrences use:

- `expired`
- `dedup_merged`
- `invalidated`
- `unknown`

Unknown is preferred to inference. If an occurrence disappears while its source
is degraded or skipped, the report is not eligible for healthy history.

Changes separate material event facts from presentation-only changes. Volatile
collection timestamps are excluded from the semantic snapshot hash.

Every report verifies:

`before + added - removed = after`

Healthy summaries are appended idempotently to
`audit/public-snapshot-delta-history.jsonl`. The detailed latest report is
`audit/public-snapshot-delta.json` and is also retained as a workflow artifact.

## OSS benchmark

The design reuses two proven patterns without adding a dependency:

- `SahirVhora/trending-repo`: persisted snapshots compared by stable key into
  entered / left / stayed sets.
- `LokeshNanda/oss-radar-ai`: generated machine-readable state retained across
  scheduled runs instead of leaving history only in workflow logs.

The repository already has stable occurrence identity and JSON tooling, so
copying a framework or adding a package would add more authority than value.
