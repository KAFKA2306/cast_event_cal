select
    source,
    source_id,
    source_url,
    canonical_url,
    source_created_at,
    first_seen_at,
    last_seen_at,
    observed_at,
    content_hash,
    decision,
    reason,
    parser_version,
    schema_version
from {{ source('canonical_read_model', 'source_records') }}
