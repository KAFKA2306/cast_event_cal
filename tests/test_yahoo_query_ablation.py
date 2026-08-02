from __future__ import annotations

import json
from pathlib import Path

from scripts import run_yahoo_query_ablation as ablation


def test_query_plan_contains_all_logical_and_lexical_ablations() -> None:
    config = json.loads(Path("config/yahoo_query_ablation.json").read_text(encoding="utf-8"))
    plan = ablation.build_query_plan(config)
    by_key = {row["key"]: row for row in plan}

    assert len(plan) == 10
    assert len({row["query"].casefold() for row in plan}) == 10
    assert set(by_key) >= {
        "abc_full",
        "ac_no_access",
        "bc_no_announcement",
        "ab_no_platform",
        "a_only",
        "b_only",
        "c_only",
        "event_announcement_access",
        "business_open_access",
        "participation_method_access",
    }
    assert "イベント告知" in by_key["abc_full"]["query"]
    assert "JOIN" in by_key["abc_full"]["query"]
    assert "VRChat" in by_key["abc_full"]["query"]
    assert "JOIN" not in by_key["ac_no_access"]["query"]
    assert "イベント告知" not in by_key["bc_no_announcement"]["query"]
    assert "VRChat" not in by_key["ab_no_platform"]["query"]


def test_enrich_calculates_block_effects_and_incremental_accepts() -> None:
    results = [
        {
            "key": "abc_full",
            "status": "ok",
            "content_acceptance_rate": 0.5,
            "content_accepted_count": 2,
            "candidate_status_ids": ["1", "2", "8", "9"],
            "content_accepted_status_ids": ["1", "2"],
        },
        {
            "key": "ac_no_access",
            "status": "ok",
            "content_acceptance_rate": 0.25,
            "content_accepted_count": 1,
            "candidate_status_ids": ["1", "3", "4", "5"],
            "content_accepted_status_ids": ["1"],
        },
        {
            "key": "bc_no_announcement",
            "status": "ok",
            "content_acceptance_rate": 0.75,
            "content_accepted_count": 2,
            "candidate_status_ids": ["2", "3", "6", "7"],
            "content_accepted_status_ids": ["2", "3"],
        },
        {
            "key": "ab_no_platform",
            "status": "ok",
            "content_acceptance_rate": 0.25,
            "content_accepted_count": 1,
            "candidate_status_ids": ["4", "10", "11", "12"],
            "content_accepted_status_ids": ["4"],
        },
    ]

    comparison = ablation.enrich(results, "abc_full")

    assert comparison["full_variant_available"] is True
    assert results[2]["incremental_accepted_vs_full_count"] == 1
    assert results[3]["exclusive_accepted_count"] == 1
    assert comparison["block_effects"]["access"] == {
        "full_key": "abc_full",
        "ablated_key": "ac_no_access",
        "precision_delta_full_minus_ablated": 0.25,
        "accepted_yield_delta_full_minus_ablated": 1,
        "accepted_lost_when_removed_count": 1,
        "accepted_gained_when_removed_count": 0,
    }
    assert comparison["block_effects"]["announcement"]["precision_delta_full_minus_ablated"] == -0.25
    assert comparison["block_effects"]["announcement"]["accepted_gained_when_removed_count"] == 1
    assert comparison["block_effects"]["platform"]["accepted_lost_when_removed_count"] == 2


def test_ratio_and_jaccard_are_zero_safe() -> None:
    assert ablation.ratio(0, 0) == 0.0
    assert ablation.jaccard(set(), set()) == 0.0
    assert ablation.jaccard({"1", "2"}, {"2", "3"}) == 0.333333
