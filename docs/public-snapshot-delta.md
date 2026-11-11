# Public snapshot delta audit

`scripts/build_public_snapshot_delta.py` compares the previous valid `public/events.json` with the new candidate by stable occurrence identity. It observes changes but does not change selection or publication.

The deterministic report contains hashes, counts, and `added`, `removed`, `changed`, `unchanged`. Additions: `new_discovery`, `recurrence_materialized`, `promoted_datetime_resolution`, `other`. Removals: `expired`, `dedup_merged`, `invalidated`, `unknown`.

Unknown reasons are not guessed. Disappearance during degraded/skipped source collection disqualifies healthy history. Volatile collection timestamps are excluded from semantic hashes. Invariant: `before + added - removed = after`.

Details: `audit/public-snapshot-delta.json`; idempotent healthy history: `audit/public-snapshot-delta-history.jsonl`.
