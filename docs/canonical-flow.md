# Canonical event publication flow

`cast_event_cal` is the canonical repository for event identity, collection, normalization, classification, ontology enrichment, acceptance/rejection state, and publication materialization. `KAFKA2306/vrc_cast_event_calender` is a projection-only distribution repository and must not independently collect, classify, or redefine event identity.

The production flow is intentionally one-way:

```text
source observations
  -> canonical candidate records
  -> deterministic classification / rejection
  -> ontology enrichment
  -> canonical published events
  -> public/events.json + public/calendar.ics + audit outputs
  -> projection repository / Pages
```

## State ownership

- Candidate observations and source-specific health live under `data/`.
- Acceptance/rejection decisions are produced by deterministic classifiers and recorded with reasons.
- Event identity and ontology ownership live in this repository.
- `public/` is a materialized projection from canonical state, not an independent source of truth.
- Canonical UI materialization such as `public/index.html` remains here because it is generated from canonical state by the canonical renderer.
- Delivery-platform runtime configuration is not canonical event state. Cloudflare Pages routing such as `_routes.json` is owned by `KAFKA2306/vrc_cast_event_calender` and must not be materialized under this repository's `public/` tree.
- `vrc_cast_event_calender` may validate and distribute these outputs, but must not own a second collector, classifier, ontology, or event-state machine.

## Repository KPIs

Only these repository-level KPIs are canonical for the ratchet contract:

1. `acceptance_precision` — measured only when reviewed outcome evidence exists; otherwise unknown.
2. `publication_freshness` — age of the latest verified canonical publication output.
3. `publication_success_rate` — successful canonical collect/classify/materialize/publish runs over observed runs.

Unknown or uninstrumented values are not converted to zero.

## Non-goals

- Duplicating the classifier or ontology in the projection repository.
- Treating candidate count as product quality.
- Adding another status store for the same event decision.
- Running unrelated research automation with write access to this repository.

## CI contract

CI must fail if the canonical ownership statement disappears, the KPI set expands beyond the three names above, an obsolete noncanonical workflow is reintroduced, or delivery-owned Cloudflare routing returns under `public/`. Existing event, ontology, provenance, MCP, and publication tests remain the authoritative functional gates.
