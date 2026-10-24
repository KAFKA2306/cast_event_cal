# Retention contract

`config/retention-policy.json` is the single machine-readable lifecycle classification for persistent data classes. `scripts/audit_retention.py` inventories repository/workflow artifacts read-only and never deletes or rewrites data.

Unknown paths are `UNCLASSIFIED` and are not eligible for automatic deletion. Generated public projections are explicitly non-canonical and replaceable; canonical provenance and accepted facts remain retained for reproducibility. Raw/rejected/unresolved source evidence and operator artifacts are only marked for future compaction review, not deletion.

Run `python scripts/audit_retention.py` for an inventory report. `--strict` fails when a scanned persistent path is unclassified or ambiguously classified. Any future compaction must first report counts, bytes, and reproducibility impact; Git history rewriting and production deletion are outside this contract.
