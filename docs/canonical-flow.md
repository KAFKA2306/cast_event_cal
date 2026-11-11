# Canonical event publication flow

`KAFKA2306/cast_event_cal` is the canonical owner of source observations, accepted/rejected candidate decisions, event identity, ontology, and materialized `public/` artifacts. `KAFKA2306/vrc_cast_event_calender` is projection/delivery only and must not collect, classify, or redefine identity.

Flow: source observations → canonical candidate records → deterministic classification/rejection → occurrence deduplication and ontology → `public/events.json` / `public/calendar.ics` / audits → delivery.

Source observations and health are in `data/`; `public/` is generated output. Cloudflare routing such as `_routes.json` belongs to the delivery repository, not canonical `public/`.

## Canonical KPIs

- `acceptance_precision`: measured only with reviewed truth evidence; otherwise unknown
- `publication_freshness`: age of last verified published snapshot
- `publication_success_rate`: successful runs divided by observed runs

Unknown values are not zero. Candidate count is not a quality metric. CI must reject a second classifier, ontology owner, delivery-only routing in canonical `public/`, or an obsolete noncanonical workflow.
