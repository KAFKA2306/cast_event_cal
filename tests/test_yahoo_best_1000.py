from __future__ import annotations

from scripts import collect_yahoo_corpus as corpus
from scripts.run_yahoo_best_1000 import (
    ALLOWED_STRUCTURED_GROUPS,
    build_best_query_plan,
    select_exact_target,
)


def test_best_plan_starts_with_ablation_winner_and_complements() -> None:
    config = corpus.read_json(corpus.CONFIG_PATH, {})
    plan = build_best_query_plan(config)
    assert [row["key"] for row in plan[:3]] == [
        "best-000-abc-full",
        "best-001-ac-complement",
        "best-002-bc-complement",
    ]
    assert len(plan) >= 100


def test_every_query_keeps_the_platform_constraint_and_excludes_noise_groups() -> None:
    config = corpus.read_json(corpus.CONFIG_PATH, {})
    plan = build_best_query_plan(config)
    assert all("VRChat" in row["query"] or "VRC" in row["query"] for row in plan)
    assert not any("commerce_noise" in row["group"] for row in plan)
    assert not any("temporal_audit" in row["group"] for row in plan)
    assert {
        row["group"].removeprefix("structured_")
        for row in plan
        if row["group"].startswith("structured_")
    } <= ALLOWED_STRUCTURED_GROUPS


def test_exact_target_prefers_earlier_queries_then_retweets() -> None:
    plan = [
        {"key": "q0", "group": "g", "term": "a", "query": "x", "url": "u"},
        {"key": "q1", "group": "g", "term": "b", "query": "y", "url": "u"},
    ]
    rows = [
        {"status_id": "3", "query_keys": ["q1"], "retweet_count": 100},
        {"status_id": "2", "query_keys": ["q0"], "retweet_count": 2},
        {"status_id": "1", "query_keys": ["q0"], "retweet_count": 10},
    ]
    selected = select_exact_target(rows, plan, 2)
    assert [row["status_id"] for row in selected] == ["1", "2"]
