from scripts.check_upstream_conclusion import classify


def test_success_is_the_only_pass():
    assert classify("success") == "pass"


def test_known_non_success_conclusions_fail_closed():
    for conclusion in (
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "stale",
        "neutral",
        "skipped",
    ):
        assert classify(conclusion) == "fail"


def test_unknown_conclusion_fails_closed():
    assert classify("future_conclusion") == "fail"
