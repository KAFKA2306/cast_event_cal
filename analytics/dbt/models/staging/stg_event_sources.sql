select
    event_id,
    source,
    source_id,
    evidence_type,
    confidence
from {{ source('canonical_read_model', 'event_sources') }}
