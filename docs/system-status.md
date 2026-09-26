# System status contract

`scripts/build_system_status.py` projects existing validated `public/health.json` and `public/snapshot.json` into a stable `public/status.json` contract for dashboards, alerts, and recovery automation.

`overall_status` is `stale` when the same snapshot-age rule used by `audit_freshness.py` fails, otherwise it is `ok` only when collection health is `ok`; other collection states are `degraded`. The projection intentionally excludes source error/reason text and private payloads.

The SLO threshold is published under `slo.max_snapshot_age_minutes` so consumers do not need to duplicate repository policy.
