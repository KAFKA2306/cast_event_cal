# Coverage recall audit

`config/coverage_gold.json` is a small provenance-backed audit fixture, not a second event database and never an input to `public/events.json`.

Run the audit with:

```bash
python scripts/audit_coverage.py --run path/to/collector-run.json --output coverage-report.json
```

The run JSON may provide `events`, `supported_sources`, `source_unavailable`, and `miss_reasons`. Each gold occurrence is classified as `found`, `not_found`, `unsupported`, or `source_unavailable`. A normal miss retains one of the machine-readable pipeline reasons; an unavailable source is excluded from the recall denominator rather than silently becoming recall zero.

For a query change, pass the previous report with `--baseline-report previous.json` to emit per-occurrence status deltas. Category and source breakdowns remain separate so a single aggregate score cannot hide a systematic gap.
