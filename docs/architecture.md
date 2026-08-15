# Architecture

## Canonical responsibility

`KAFKA2306/cast_event_cal` is the source of truth for collection, normalization, classification, event identity, occurrence deduplication, ontology, and the canonical `public/` snapshot.

`KAFKA2306/vrc_cast_event_calender` is projection/delivery only. It must not implement an independent collector, classifier, ontology, or semantic deduplicator.

## Canonical data flow

```text
source collection
  -> normalization
  -> exact source-record deduplication
  -> source/link/asset enrichment
  -> canonical occurrence deduplication
  -> ontology/category enrichment
  -> public JSON + ICS + audits
  -> projection repository
```

### 1. Source collection

Collectors write source-specific observations under `data/`. Each source record keeps a stable provider identity where available, such as an X status ID, VRChat calendar event ID, ICS UID, or curated manual source ID.

### 2. Normalization and exact source-record deduplication

`cast_event_cal/core.py` owns normalization and exact event-ID deduplication during the normalized calendar build. This phase only removes duplicate representations of the same source record.

It does **not** decide that two different source posts describe one real-world event occurrence.

### 3. Canonical occurrence deduplication

`scripts/deduplicate_occurrences.py` is the authority for semantic occurrence resolution after source/link/asset enrichment and before frontend/ontology publication.

It separates:

- `source_record_id`: one provider/source observation;
- `occurrence_id`: one user-visible event occurrence;
- `provenance[]`: all source observations collapsed into the occurrence.

Automatic merging is intentionally conservative. High-confidence evidence includes:

- the same source record;
- the same canonical event URL and start time;
- the same normalized description and start time;
- the same sufficiently specific title and start time;
- the same organizer, start time, occurrence ordinal, and sufficiently similar announcement text;
- the same organizer/start time with a high announcement-text similarity threshold.

Title similarity alone is not sufficient. Different dates, different ordinal numbers, or different organizers remain separate unless stronger evidence exists.

The deduplicator writes `public/event-duplicate-audit.json` with before/after counts, duplicate clusters, merge reasons, confidence, ambiguous candidates, and negative-control samples.

### 4. Publication gate

`.github/workflows/update-calendar-v2.yml` runs the occurrence deduplicator before `scripts/render_frontend.py` and validates:

- every published row has `source_record_id` and `occurrence_id`;
- `occurrence_id` is unique in `public/events.json`;
- ICS UID count equals the published event count;
- ICS UIDs are unique;
- duplicate-audit before/after counts reconcile exactly.

This makes `1 occurrence = 1 JSON row = 1 VEVENT` a publish-time invariant.

## Identity policy

Source identity and occurrence identity are deliberately distinct.

A new repost, reminder post, or alternate source does not automatically create a new public event if deterministic evidence shows it refers to an already-known occurrence. Conversely, events are not merged merely because their titles are similar.

For merged occurrences, all original source IDs and URLs remain available through `provenance[]` so deduplication never destroys source traceability.

## Generated artifacts

The canonical publication surface is `public/`. Important artifacts include:

- `public/events.json`
- `public/calendar.ics`
- `public/health.json`
- `public/event-duplicate-audit.json`
- `public/event-ontology.json`
- `public/category-ontology.json`
- other source/classification/link/asset audit files

Generated artifacts are evidence of a specific canonical run; they are not stronger than the source records and deterministic rules that produced them.
