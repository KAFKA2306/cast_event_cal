# Event series ontology

## Purpose

`config/event_ontology.json` is the human-curated source of truth for recurring and irregular VRChat event series. Search and ingestion jobs may link observed announcements to an existing entry, but they must never create, rewrite, or expand curated entries automatically.

The separation is intentional:

- **Human curation:** identity, official pages, series introduction, cadence, highlights, first-time guidance, official imagery, and review provenance.
- **Mechanical processing:** exact/alias matching, enrichment of each observed event, display, auditing, and unmatched/ambiguous queues.

## Matching policy

Matching remains fail-closed. A result is linked only when either:

1. an explicit alias occurs in the title or description; or
2. the organizer matches exactly and all `required_patterns` are present.

Pattern-only and fuzzy matching are prohibited. Ambiguous matches are rejected and sent to the audit output.

## Curated entry fields

Each entry may contain:

- `canonical_id`, `canonical_name`
- `aliases`, `organizers`, `required_patterns`
- `category`, `subcategory`
- `official_links`: official website, VRChat Group, official X, Discord information page, participation guide, or other verified first-party page
- `official_image`: optional first-party image URL, alt text, and kind
- `schedule`: `recurring`, `irregular`, or `one_off`, plus a user-facing label, cadence text, and caveat
- `introduction`: stable description of the series rather than copy from one announcement
- `highlights`: concise reasons to attend
- `first_time_guide`: stable guidance for a first visit
- `participation_method`, `event_format`, `audience`, `default_location`, `tags`
- `curation`: human-review status, review date, and source URLs used to verify the profile

## Governance

1. Add or change entries only by reviewed pull request.
2. Prefer first-party URLs. Do not infer a VRChat Group URL or website from a name.
3. Treat current announcement text as event-instance data, not ontology data.
4. Use `schedule.note` to state that the current announcement overrides the usual cadence.
5. Keep promotional prose factual and stable. Avoid copying long text from external pages.
6. Review stale links and cadence periodically; do not silently replace them during ingestion.

## Enriched event contract

A matched event receives:

- `ontology_id`
- `canonical_name`
- merged `official_links`
- `series_profile`, containing the curated schedule, introduction, highlights, first-time guide, image, and curation status
- stable participation, format, audience, location, and tags

The current announcement remains the primary action link. Curated links supplement it and explain the wider event series.
