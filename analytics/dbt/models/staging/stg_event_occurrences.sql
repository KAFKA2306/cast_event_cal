select
    event_id,
    title,
    starts_at,
    ends_at,
    organizer_id,
    series_id,
    category,
    participation_url,
    lifecycle
from {{ source('canonical_read_model', 'event_occurrences') }}
