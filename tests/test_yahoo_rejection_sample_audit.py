from scripts.build_yahoo_rejection_sample_audit import build


def test_build_samples_every_reason_and_prefers_high_retweets() -> None:
    rows = [
        {"status_id": "1", "reason": "missing_datetime", "retweet_count": 2, "text_excerpt": "a"},
        {"status_id": "2", "reason": "missing_datetime", "retweet_count": 9, "text_excerpt": "b"},
        {"status_id": "3", "reason": "product_only", "retweet_count": 4, "text_excerpt": "c"},
    ]
    payload = build(rows)
    assert payload["materialized_rejected_count"] == 3
    assert payload["reason_count"] == 2
    reasons = {row["reason"]: row for row in payload["reasons"]}
    assert reasons["missing_datetime"]["count_in_materialized_rejected_file"] == 2
    assert reasons["missing_datetime"]["samples"][0]["status_id"] == "2"
    assert reasons["product_only"]["samples"][0]["status_id"] == "3"


def test_build_truncates_public_excerpt() -> None:
    payload = build([
        {"status_id": "1", "reason": "not_vrchat", "text_excerpt": "x" * 500}
    ])
    assert len(payload["reasons"][0]["samples"][0]["text_excerpt"]) == 360
