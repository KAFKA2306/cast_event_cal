from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as implementation
from scripts import refine_yahoo_corpus as refinement
from scripts import run_yahoo_realtime as ledger

AUDIT_PATH = Path("public/yahoo-best-1000-audit.json")
RAW_PATH = Path("data/yahoo-best-1000-raw.json")
EVENTS_PATH = Path("data/yahoo-best-1000-events.json")
DEFAULT_TARGET = 1000
DEFAULT_MAX_QUERIES = 180
DEFAULT_DELAY_SECONDS = 0.35
ALLOWED_STRUCTURED_GROUPS = {
    "core",
    "access",
    "venues",
    "activities",
    "communities",
    "recruitment",
}
FALLBACK_GROUPS = ("activities", "communities", "venues", "core")

ACCESS_BLOCK = (
    "JOIN OR ジョイン OR リクイン OR reqin OR リクエストインバイト OR "
    '"request invite" OR Group+ OR グループインスタンス OR '
    "フレンドインスタンス OR 参加方法"
)
ANNOUNCEMENT_BLOCK = "イベント告知 OR 営業告知 OR 通常営業 OR 開催決定 OR OPEN OR オープン"
PLATFORM_BLOCK = "VRChat OR VRC"
CONTEXT_BLOCK = "開催 OR 告知 OR 日時 OR OPEN OR オープン OR 開場 OR 開始 OR 営業 OR 本日 OR 今日 OR 明日 OR 今夜"

PROVEN_QUERIES: tuple[dict[str, str], ...] = (
    {
        "key": "best-000-abc-full",
        "group": "ablation_winner",
        "term": "A+B+C",
        "query": f"({ANNOUNCEMENT_BLOCK}) ({ACCESS_BLOCK}) ({PLATFORM_BLOCK})",
    },
    {
        "key": "best-001-ac-complement",
        "group": "ablation_complement",
        "term": "A+C",
        "query": f"({ANNOUNCEMENT_BLOCK}) ({PLATFORM_BLOCK})",
    },
    {
        "key": "best-002-bc-complement",
        "group": "ablation_complement",
        "term": "B+C",
        "query": f"({ACCESS_BLOCK}) ({PLATFORM_BLOCK})",
    },
    {
        "key": "best-003-event-announcement-access",
        "group": "lexical_high_precision",
        "term": "イベント告知系",
        "query": (
            "(イベント告知 OR 開催決定 OR 集会 OR 交流会 OR 公演 OR ライブイベント) "
            f"({ACCESS_BLOCK}) ({PLATFORM_BLOCK})"
        ),
    },
    {
        "key": "best-004-business-open-access",
        "group": "lexical_high_precision",
        "term": "営業・OPEN系",
        "query": (
            "(営業告知 OR 通常営業 OR OPEN OR オープン OR カフェ営業 OR バー営業) "
            f"({ACCESS_BLOCK}) ({PLATFORM_BLOCK})"
        ),
    },
    {
        "key": "best-005-participation-method",
        "group": "lexical_high_precision",
        "term": "参加方法系",
        "query": (
            "(参加方法 OR JOIN制 OR リクイン OR Group+ instance OR グループインスタンス) "
            f"({CONTEXT_BLOCK}) ({PLATFORM_BLOCK})"
        ),
    },
)


def make_url(query: str) -> str:
    return "https://search.yahoo.co.jp/realtime/search?" + urlencode(
        {"ei": "UTF-8", "p": query, "md": "h"}
    )


def add_query(plan: list[dict[str, str]], seen: set[str], row: dict[str, str]) -> None:
    query = str(row.get("query") or "").strip()
    folded = query.casefold()
    if not query or folded in seen:
        return
    if "vrchat" not in folded and "vrc" not in folded:
        raise ValueError(f"best-1000 query lacks platform constraint: {row.get('key')}")
    seen.add(folded)
    item = dict(row)
    item["url"] = make_url(query)
    plan.append(item)


def build_best_query_plan(config: dict[str, Any]) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in PROVEN_QUERIES:
        add_query(plan, seen, dict(row))

    for row in corpus.build_query_plan(config):
        group = str(row.get("group") or "")
        if group not in ALLOWED_STRUCTURED_GROUPS:
            continue
        item = dict(row)
        item["key"] = f"best-structured-{item['key']}"
        item["group"] = f"structured_{group}"
        add_query(plan, seen, item)

    groups = config.get("term_groups", {})
    if not isinstance(groups, dict):
        raise ValueError("term_groups must be an object")
    fallback_index = 0
    for group in FALLBACK_GROUPS:
        values = groups.get(group, [])
        if not isinstance(values, list):
            continue
        for raw in values:
            term = str(raw).strip()
            if not term:
                continue
            add_query(
                plan,
                seen,
                {
                    "key": f"best-fallback-{fallback_index:03d}",
                    "group": f"platform_fallback_{group}",
                    "term": term,
                    "query": f"({term}) ({PLATFORM_BLOCK})",
                },
            )
            fallback_index += 1

    if len(plan) < 100:
        raise ValueError(f"best-1000 plan is too small: {len(plan)}")
    return plan


def candidate_priority(row: dict[str, Any], plan_index: dict[str, int]) -> tuple[int, int, str]:
    query_keys = [str(value) for value in row.get("query_keys", [])]
    first_index = min((plan_index.get(key, 10**9) for key in query_keys), default=10**9)
    try:
        retweets = int(row.get("retweet_count") or 0)
    except (TypeError, ValueError):
        retweets = 0
    return first_index, -retweets, str(row.get("status_id") or "")


def select_exact_target(
    rows: list[dict[str, Any]], plan: list[dict[str, str]], target: int
) -> list[dict[str, Any]]:
    plan_index = {row["key"]: index for index, row in enumerate(plan)}
    selected = sorted(rows, key=lambda row: candidate_priority(row, plan_index))[:target]
    if len({str(row.get("status_id")) for row in selected}) != len(selected):
        raise ValueError("duplicate status IDs remained after collection")
    return selected


def evaluate_candidates(
    rows: list[dict[str, Any]], *, now: datetime, min_retweets: int, x_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    content_events: list[dict[str, Any]] = []
    production_events: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()

    for original in rows:
        row = dict(original)
        status_id = str(row.get("status_id") or "")
        source_created_at = refinement.twitter_snowflake_created_at(status_id)
        anchor = source_created_at or now
        if source_created_at:
            row["source_created_at"] = implementation.utc_text(source_created_at)
        candidate = {
            "status_id": status_id,
            "url": row.get("url"),
            "text": row.get("text"),
            "author": row.get("author"),
            "retweet_count": row.get("retweet_count"),
        }
        text = str(candidate.get("text") or "")
        if refinement.giveaway_without_event_access(text):
            event, reason = None, "giveaway_only"
        else:
            event, reason = corpus.refined_candidate_to_event(
                candidate,
                now=anchor,
                min_retweets=min_retweets,
                x_ids=set(),
            )
        if event:
            start = implementation.parse_instant(str(event.get("starts_at") or ""))
            if start is None:
                event, reason = None, "missing_datetime"
            elif start < now - timedelta(hours=12):
                event, reason = None, "past_event_now"
            elif start > now + timedelta(days=180):
                event, reason = None, "too_far_future_now"
        if event:
            content_events.append(event)
            if status_id in x_ids:
                row["decision"] = "duplicate_x_source"
                row["reason"] = "duplicate_x_source"
                reasons["duplicate_x_source"] += 1
            else:
                production_events.append(event)
                row["decision"] = "accepted"
                row["reason"] = None
        else:
            resolved = reason or "unknown"
            row["decision"] = "rejected"
            row["reason"] = resolved
            reasons[resolved] += 1
        evaluated.append(row)

    content_events.sort(key=lambda item: (str(item.get("starts_at")), str(item.get("source_id"))))
    production_events.sort(key=lambda item: (str(item.get("starts_at")), str(item.get("source_id"))))
    return content_events, production_events, evaluated, reasons


def query_metrics(
    plan: list[dict[str, str]],
    query_results: list[dict[str, Any]],
    evaluated: list[dict[str, Any]],
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    result_by_key = {str(row.get("key")): row for row in query_results}
    metrics: list[dict[str, Any]] = []
    for query in plan:
        key = query["key"]
        fetched = result_by_key.get(key)
        if fetched is None:
            continue
        matching = [row for row in evaluated if key in set(row.get("query_keys", []))]
        accepted = [row for row in matching if row.get("decision") == "accepted"]
        metrics.append(
            {
                "key": key,
                "group": query["group"],
                "term": query["term"],
                "status": fetched.get("status"),
                "raw_candidates": int(fetched.get("raw_candidates") or 0),
                "target_candidates": len(matching),
                "new_to_ledger": sum(str(row.get("status_id")) not in existing_ids for row in matching),
                "accepted": len(accepted),
                "accepted_rate": round(len(accepted) / len(matching), 6) if matching else 0.0,
            }
        )
    return metrics


def update_production_ledger(
    selected: list[dict[str, Any]], *, before: list[dict[str, Any]], now: datetime
) -> None:
    history_payload = corpus.read_json(ledger.HISTORY_PATH, {})
    if not isinstance(history_payload, dict):
        history_payload = {}
    merged = ledger.merge_history(before, selected, now)
    merged = corpus.merge_provenance(merged, before, selected, now)
    history_payload.update(
        {
            "schema_version": "2.3",
            "generated_at": implementation.utc_text(now),
            "candidate_count": len(merged),
            "target_count": int(history_payload.get("target_count") or 1000),
            "target_reached": len(merged) >= int(history_payload.get("target_count") or 1000),
            "retention_days": int(history_payload.get("retention_days") or 365),
            "maximum_candidates": int(history_payload.get("maximum_candidates") or 5000),
            "source_time_policy": "x_snowflake_created_at_then_first_seen_at",
            "giveaway_policy": "require_specific_event_or_vrchat_access_method",
            "candidates": merged,
        }
    )
    implementation.write_json(ledger.HISTORY_PATH, history_payload)
    refinement.main()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET)
    parser.add_argument("--max-queries", type=int, default=DEFAULT_MAX_QUERIES)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--require-target", action="store_true")
    parser.add_argument("--no-update-production", action="store_true")
    args = parser.parse_args(argv)

    if args.target <= 0:
        raise ValueError("target must be positive")
    corpus.configure_classifier()
    now = datetime.now(UTC).replace(microsecond=0)
    config = corpus.read_json(corpus.CONFIG_PATH, {})
    if not isinstance(config, dict):
        raise ValueError("Yahoo query config must be an object")
    plan = build_best_query_plan(config)[: max(1, args.max_queries)]
    observed, query_results, raw_total = corpus.fetch_candidates(
        plan,
        set(),
        args.target,
        True,
        max(0.0, args.delay_seconds),
    )
    successful = sum(row.get("status") == "ok" for row in query_results)
    target_reached = len(observed) >= args.target
    if args.require_target and not target_reached:
        raise RuntimeError(
            f"best-1000 target not reached: {len(observed)}/{args.target}; "
            f"queries={len(query_results)} successful={successful}"
        )

    selected = select_exact_target(observed, plan, min(args.target, len(observed)))
    before = ledger.read_history()
    existing_ids = {str(row.get("status_id")) for row in before}
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    content_events, production_events, evaluated, reasons = evaluate_candidates(
        selected,
        now=now,
        min_retweets=min_retweets,
        x_ids=x_ids,
    )
    metrics = query_metrics(plan, query_results, evaluated, existing_ids)

    audit = {
        "schema_version": "1.0",
        "generated_at": implementation.utc_text(now),
        "classifier_version": implementation.PARSER_VERSION,
        "strategy_version": "ablation-informed-1.0",
        "status": "ok" if target_reached else "partial",
        "target_count": args.target,
        "target_reached": target_reached,
        "candidate_count": len(selected),
        "raw_candidate_observations": raw_total,
        "duplicate_observations_removed": max(0, raw_total - len(observed)),
        "queries_planned": len(plan),
        "queries_attempted": len(query_results),
        "queries_succeeded": successful,
        "queries_failed": len(query_results) - successful,
        "content_accepted_count": len(content_events),
        "content_acceptance_rate": round(len(content_events) / len(selected), 6) if selected else 0.0,
        "production_accepted_count": len(production_events),
        "production_acceptance_rate": round(len(production_events) / len(selected), 6) if selected else 0.0,
        "new_to_existing_ledger_count": sum(
            str(row.get("status_id")) not in existing_ids for row in evaluated
        ),
        "new_accepted_to_existing_ledger_count": sum(
            row.get("decision") == "accepted" and str(row.get("status_id")) not in existing_ids
            for row in evaluated
        ),
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "strategy": {
            "primary": "A+B+C full query",
            "complements": ["A+C", "B+C"],
            "structured_shards": sorted(ALLOWED_STRUCTURED_GROUPS),
            "fallback": "event-specific term + VRChat/VRC only",
            "excluded": ["A only", "B only", "C only", "A+B without VRChat/VRC"],
            "selection": "query priority, then retweet count, then status ID",
            "deduplication_key": "X/Twitter status ID",
            "exact_target": True,
        },
        "query_metrics": metrics,
        "quality": {
            "duplicate_status_ids": len(selected)
            - len({str(row.get("status_id")) for row in selected}),
            "missing_query_provenance": sum(not row.get("query_keys") for row in selected),
            "missing_source_created_at": sum(not row.get("source_created_at") for row in evaluated),
            "ambiguous_decisions": sum(
                row.get("decision") not in {"accepted", "rejected", "duplicate_x_source"}
                for row in evaluated
            ),
        },
    }
    implementation.write_json(AUDIT_PATH, audit)
    implementation.write_json(EVENTS_PATH, production_events)
    implementation.write_json(
        RAW_PATH,
        {
            "schema_version": "1.0",
            "generated_at": audit["generated_at"],
            "strategy_version": audit["strategy_version"],
            "target_count": args.target,
            "candidate_count": len(evaluated),
            "query_results": query_results,
            "candidates": evaluated,
        },
    )

    if not args.no_update_production:
        update_production_ledger(selected, before=before, now=now)

    print(
        "Yahoo best-1000: "
        f"candidates={len(selected)} accepted={len(production_events)} "
        f"new={audit['new_to_existing_ledger_count']} "
        f"queries={len(query_results)} status={audit['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
