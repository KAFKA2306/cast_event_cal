select
    decision,
    count(*) as source_record_count
from {{ ref('stg_source_records') }}
group by decision
