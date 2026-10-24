# Recurrence clause safety

Recurring-event extraction must not borrow a clock from a later recurrence clause. A match is rejected when it consumes an independent later recurrence marker before its clock.

Compound monthly ordinal expressions such as `毎月第2、第4日曜13時` are one recurrence clause, not two. `RECURRENCE_MARKER_RE` therefore treats `毎月` immediately followed by an ordinal weekday marker as part of the ordinal marker.

Regression coverage lives in `tests/test_recurrence_clause_boundary.py`. Release verification requires zero loss of already accepted Yahoo source events and zero provenance gaps.