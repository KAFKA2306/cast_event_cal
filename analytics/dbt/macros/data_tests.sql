{% test unique_pair(model, left_column, right_column) %}
select
    {{ left_column }},
    {{ right_column }},
    count(*) as row_count
from {{ model }}
group by {{ left_column }}, {{ right_column }}
having count(*) > 1
{% endtest %}

{% test valid_interval(model, start_column, end_column) %}
select *
from {{ model }}
where {{ start_column }} is not null
  and {{ end_column }} is not null
  and {{ end_column }} < {{ start_column }}
{% endtest %}
