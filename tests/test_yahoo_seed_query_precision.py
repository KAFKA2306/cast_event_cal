from pathlib import Path

from scripts.collect_yahoo_corpus import build_query_plan, read_json


def test_primary_seed_query_requires_event_context_and_platform() -> None:
    config = read_json(Path("config/yahoo_query_terms.json"), {})
    query = config["base_queries"][0]

    assert "(VRChat OR VRC)" in query
    assert "(開催 OR 告知 OR 日時" in query
    assert "JOIN" in query
    assert "Group+" in query


def test_negative_feedback_does_not_become_hard_query_exclusions() -> None:
    config = read_json(Path("config/yahoo_query_terms.json"), {})
    plan = build_query_plan(config)
    queries = [row["query"] for row in plan]

    assert all(" -販売" not in query for query in queries)
    assert all(" -プレゼント" not in query for query in queries)
    assert config["negative_feedback"]["policy"] == "use_for_query_structure_and_audit_only"
