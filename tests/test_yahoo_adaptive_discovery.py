"""Tests of evidence-based Yahoo discovery selection, independent of network fetches."""

from datetime import UTC, datetime, timedelta

from scripts.collect_yahoo_corpus import select_ablation_queries, select_daily_plan


NOW = datetime(2026, 11, 10, 5, 0, tzinfo=UTC)
PLATFORM = "(VRChat OR VRC)"
ANNOUNCEMENT = "(イベント告知 OR OPEN)"
ACCESS = "(JOIN OR リクイン)"
AC = f"{ANNOUNCEMENT} {PLATFORM}"
BC = f"{ACCESS} {PLATFORM}"
AB = f"{ANNOUNCEMENT} {ACCESS}"


def evidence():
    experiment = {
        "blocks": {"announcement": ANNOUNCEMENT, "access": ACCESS, "platform": PLATFORM},
        "variants": [
            {"key": "ac", "blocks": ["announcement", "platform"]},
            {"key": "bc", "blocks": ["access", "platform"]},
            {"key": "ab", "blocks": ["announcement", "access"]},
        ],
    }
    report = {
        "status": "ok",
        "generated_at": (NOW - timedelta(hours=2)).isoformat(),
        "variants": [
            {"key": "ac", "status": "ok", "query": AC, "new_to_ledger_count": 12, "production_accepted_count": 7, "new_production_accepted_count": 3},
            {"key": "bc", "status": "ok", "query": BC, "new_to_ledger_count": 10, "production_accepted_count": 5, "new_production_accepted_count": 2},
            {"key": "ab", "status": "ok", "query": AB, "new_to_ledger_count": 40, "production_accepted_count": 20, "new_production_accepted_count": 18},
        ],
    }
    return report, experiment


def test_production_selects_measured_novel_queries_with_platform_constraint():
    report, experiment = evidence()
    selected = select_ablation_queries([], report=report, experiment=experiment, now=NOW)
    assert [row["key"] for row in selected] == ["ablation-ac", "ablation-bc"]
    assert all(PLATFORM in row["query"] for row in selected)
    assert all(row["url"].startswith("https://search.yahoo.co.jp/realtime/search?") for row in selected)


def test_stale_and_future_experiment_results_are_not_used():
    report, experiment = evidence()
    report["generated_at"] = (NOW - timedelta(hours=37)).isoformat()
    assert select_ablation_queries([], report=report, experiment=experiment, now=NOW) == []
    report["generated_at"] = (NOW + timedelta(minutes=1)).isoformat()
    assert select_ablation_queries([], report=report, experiment=experiment, now=NOW) == []


def test_evidence_must_match_versioned_experiment_and_not_duplicate_active_queries():
    report, experiment = evidence()
    report["variants"][1]["query"] = "changed by some other experiment"
    selected = select_ablation_queries(
        [{"query": AC}], report=report, experiment=experiment, now=NOW
    )
    assert selected == []


def test_no_measured_novel_acceptances_means_no_auto_expansion():
    report, experiment = evidence()
    for row in report["variants"]:
        row["new_production_accepted_count"] = 0
    assert select_ablation_queries([], report=report, experiment=experiment, now=NOW) == []


def test_hourly_rotation_expands_distinct_source_coverage_without_extra_queries():
    base = [{"key": "base", "group": "base", "query": "core"}]
    production = [
        {"key": f"production-{n}", "group": "activities", "query": str(n)}
        for n in range(40)
    ]
    audit = [
        {"key": f"audit-{n}", "group": "temporal_audit", "query": str(n)}
        for n in range(6)
    ]
    plan = base + production + audit
    first = select_daily_plan(plan, NOW, 8)
    next_hour = select_daily_plan(plan, NOW + timedelta(hours=1), 8)
    assert len(first) == len(next_hour) == 9
    assert first[0]["key"] == next_hour[0]["key"] == "base"
    assert {row["key"] for row in first} != {row["key"] for row in next_hour}
    assert all(row["key"] != "base" for row in first[1:])


def test_yahoo_query_yield_prioritizes_proven_exclusive_event_hits():
    base = [{"key": "base-0", "group": "base", "query": "base"}]
    production = [
        {"key": f"core-{n:03d}", "group": "core", "query": f"query-{n}"}
        for n in range(40)
    ]
    audit = [
        {"key": f"audit-{n}", "group": "temporal_audit", "query": f"audit-{n}"}
        for n in range(4)
    ]
    yield_report = {
        "queries": [
            {"query_key": "core-003", "classification": "productive", "unique_only_accepted": 6, "observed_candidates": 20},
            {"query_key": "core-004", "classification": "productive", "unique_only_accepted": 5, "observed_candidates": 20},
            {"query_key": "core-005", "classification": "productive", "unique_only_accepted": 4, "observed_candidates": 20},
            {"query_key": "audit-1", "classification": "productive", "unique_only_accepted": 40, "observed_candidates": 40},
            {"query_key": "missing-key", "classification": "productive", "unique_only_accepted": 40, "observed_candidates": 40},
            {"query_key": "core-006", "classification": "high-noise", "unique_only_accepted": 100, "observed_candidates": 100},
        ]
    }
    classifier = {"generated_at": (NOW - timedelta(hours=1)).isoformat()}
    first = select_daily_plan(
        base + production + audit, NOW, 18,
        yield_audit=yield_report, classifier_audit=classifier,
    )
    assert len(first) == 1 + 16 + 2
    assert [row["key"] for row in first[1:4]] == ["core-003", "core-004", "core-005"]
    second = select_daily_plan(
        base + production + audit, NOW + timedelta(hours=1), 18,
        yield_audit=yield_report, classifier_audit=classifier,
    )
    assert len(second) == len(first)
    assert {row["key"] for row in first} != {row["key"] for row in second}
    assert len({row["key"] for row in first}) == len(first)


def test_yahoo_yield_uses_fresh_classifier_provenance_only():
    plan = [
        {"key": f"core-{n:03d}", "group": "core", "query": str(n)}
        for n in range(20)
    ]
    yield_report = {"queries": [
        {"query_key": "core-019", "classification": "productive", "unique_only_accepted": 10, "observed_candidates": 10}
    ]}
    stale = {"generated_at": (NOW - timedelta(hours=48)).isoformat()}
    future = {"generated_at": (NOW + timedelta(minutes=1)).isoformat()}
    baseline = select_daily_plan(plan, NOW, 8)
    assert select_daily_plan(plan, NOW, 8, yield_audit=yield_report, classifier_audit=stale) == baseline
    assert select_daily_plan(plan, NOW, 8, yield_audit=yield_report, classifier_audit=future) == baseline
    assert select_daily_plan(plan, NOW, 8, yield_audit={}, classifier_audit={"generated_at": NOW.isoformat()}) == baseline
