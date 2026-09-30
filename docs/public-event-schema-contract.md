# Public event schema compatibility

`public/events.json` is a public consumer contract. `scripts/audit_public_event_schema.py` inventories the complete current event set without changing it and reports field types, nullability, presence, repository consumer dependencies, and a content-derived snapshot identity.

The initial fail-closed compatibility floor is intentionally small: `id`, `title`, and `starts_at` must exist on every public event and remain strings. Optional additive fields are compatible. Missing required fields and type drift are breaking candidates and report the affected repository consumers. Unknown optional fields are retained in the inventory rather than rejected.

The audit never invents defaults for missing facts and does not change publication, ranking, collection, or event identity. Schema/version changes and legacy-alias removal require a separate explicit change.