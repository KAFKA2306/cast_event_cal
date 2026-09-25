select
    run_id,
    started_at,
    completed_at,
    source,
    status,
    fetched_count,
    accepted_count,
    rejected_count
from {{ ref('stg_collection_runs') }}
