from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import collect_yahoo_corpus as corpus
from scripts import fetch_yahoo_realtime as yahoo
from scripts import refine_yahoo_corpus as refinement
from scripts import run_yahoo_realtime as ledger

CONFIG_PATH = Path("config/yahoo_query_ablation.json")
PUBLIC_PATH = Path("public/yahoo-query-ablation.json")
RAW_PATH = Path("data/yahoo-query-ablation-raw.json")
_PRIVATE_FIELDS = {
    "candidate_status_ids",
    "content_accepted_status_ids",
    "production_accepted_status_ids",
}


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def jaccard(left: set[str], right: set[str]) -> float:
    return ratio(len(left & right), len(left | right))


def build_query_plan(config: dict[str, Any]) -> list[dict[str, str]]:
    blocks, variants = config.get("blocks"), config.get("variants")
    if not isinstance(blocks, dict) or not isinstance(variants, list):
        raise ValueError("Ablation config requires blocks and variants")
    plan, keys, queries = [], set(), set()
    for item in variants:
        if not isinstance(item, dict):
            raise ValueError("Each variant must be an object")
        key = str(item.get("key") or "").strip()
        if not key or key in keys:
            raise ValueError(f"Duplicate or empty variant key: {key!r}")
        query = str(item.get("query") or "").strip()
        if not query:
            names = item.get("blocks")
            if not isinstance(names, list) or not names:
                raise ValueError(f"Variant {key} requires query or blocks")
            missing = [str(name) for name in names if str(name) not in blocks]
            if missing:
                raise ValueError(f"Variant {key} has unknown blocks: {missing}")
            query = " ".join(str(blocks[str(name)]).strip() for name in names)
        if query.casefold() in queries:
            raise ValueError(f"Duplicate query for {key}")
        keys.add(key)
        queries.add(query.casefold())
        plan.append(
            {
                "key": key,
                "label": str(item.get("label") or key),
                "kind": str(item.get("kind") or "unspecified"),
                "query": query,
                "url": "https://search.yahoo.co.jp/realtime/search?"
                + urlencode({"ei": "UTF-8", "p": query, "md": "h"}),
            }
        )
    if str(config.get("full_variant_key")) not in keys:
        raise ValueError("full_variant_key must reference a variant")
    return plan


def evaluate(
    candidates: list[dict[str, Any]], now: datetime, minimum_retweets: int, x_ids: set[str]
) -> tuple[set[str], Counter[str]]:
    observed_at = yahoo.utc_text(now)
    rows = [
        {
            **row,
            "first_seen_at": observed_at,
            "last_seen_at": observed_at,
            "observation_count": 1,
            "max_retweet_count": row.get("retweet_count") or 0,
        }
        for row in candidates
    ]
    accepted, _rejected, evaluated = refinement.reevaluate_with_source_time(
        rows, actual_now=now, min_retweets=minimum_retweets, x_ids=x_ids
    )
    accepted_ids = {str(row.get("source_id", "")).split(":")[-1] for row in accepted}
    reasons = Counter(
        str(row.get("last_reason") or "unknown")
        for row in evaluated
        if row.get("last_decision") != "accepted"
    )
    return accepted_ids, reasons


def fetch_variant(
    variant: dict[str, str],
    *,
    now: datetime,
    minimum_retweets: int,
    result_limit: int,
    ledger_ids: set[str],
    x_ids: set[str],
) -> dict[str, Any]:
    started = time.monotonic()
    yahoo.validate_search_url(variant["url"])
    html, status, final_url = yahoo.fetch_page(variant["url"])
    candidates = list({str(row["status_id"]): row for row in yahoo.extract_candidates(html)}.values())
    if not candidates:
        raise RuntimeError("no direct Yahoo post objects")
    candidate_ids = {str(row["status_id"]) for row in candidates}
    content_ids, reasons = evaluate(candidates, now, minimum_retweets, set())
    production_ids, _ = evaluate(candidates, now, minimum_retweets, x_ids)
    new_ids = candidate_ids - ledger_ids
    return {
        **{name: variant[name] for name in ("key", "label", "kind", "query")},
        "status": "ok",
        "http_status": status,
        "final_url": final_url,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "candidate_count": len(candidate_ids),
        "result_limit": result_limit,
        "result_limit_reached": len(candidate_ids) >= result_limit,
        "new_to_ledger_count": len(new_ids),
        "new_to_ledger_rate": ratio(len(new_ids), len(candidate_ids)),
        "content_accepted_count": len(content_ids),
        "content_acceptance_rate": ratio(len(content_ids), len(candidate_ids)),
        "production_accepted_count": len(production_ids),
        "production_acceptance_rate": ratio(len(production_ids), len(candidate_ids)),
        "new_content_accepted_count": len(content_ids & new_ids),
        "new_production_accepted_count": len(production_ids & new_ids),
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "candidate_status_ids": sorted(candidate_ids),
        "content_accepted_status_ids": sorted(content_ids),
        "production_accepted_status_ids": sorted(production_ids),
    }


def enrich(results: list[dict[str, Any]], full_key: str) -> dict[str, Any]:
    successful = {str(row["key"]): row for row in results if row.get("status") == "ok"}
    full = successful.get(full_key)
    if full is None:
        return {"full_variant_available": False, "block_effects": {}}
    full_candidates = set(full["candidate_status_ids"])
    full_accepted = set(full["content_accepted_status_ids"])
    accepted_by_key = {
        key: set(row["content_accepted_status_ids"]) for key, row in successful.items()
    }
    for key, row in successful.items():
        candidates, accepted = set(row["candidate_status_ids"]), accepted_by_key[key]
        others = set().union(*(values for other, values in accepted_by_key.items() if other != key))
        row.update(
            {
                "candidate_overlap_with_full_count": len(candidates & full_candidates),
                "candidate_jaccard_with_full": jaccard(candidates, full_candidates),
                "accepted_overlap_with_full_count": len(accepted & full_accepted),
                "accepted_jaccard_with_full": jaccard(accepted, full_accepted),
                "incremental_accepted_vs_full_count": len(accepted - full_accepted),
                "exclusive_accepted_count": len(accepted - others),
            }
        )
    effects = {}
    for block, ablated_key in {
        "access": "ac_no_access",
        "announcement": "bc_no_announcement",
        "platform": "ab_no_platform",
    }.items():
        ablated = successful.get(ablated_key)
        if not ablated:
            continue
        ablated_ids = set(ablated["content_accepted_status_ids"])
        effects[block] = {
            "full_key": full_key,
            "ablated_key": ablated_key,
            "precision_delta_full_minus_ablated": round(
                float(full["content_acceptance_rate"])
                - float(ablated["content_acceptance_rate"]),
                6,
            ),
            "accepted_yield_delta_full_minus_ablated": int(full["content_accepted_count"])
            - int(ablated["content_accepted_count"]),
            "accepted_lost_when_removed_count": len(full_accepted - ablated_ids),
            "accepted_gained_when_removed_count": len(ablated_ids - full_accepted),
        }
    return {"full_variant_available": True, "block_effects": effects}


def run(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = corpus.read_json(config_path, {})
    if not isinstance(config, dict):
        raise ValueError("Ablation config must be an object")
    corpus.configure_classifier()
    yahoo.PARSER_VERSION = str(config.get("classifier_version") or yahoo.PARSER_VERSION)
    now = datetime.now(UTC).replace(microsecond=0)
    minimum_retweets = int(config.get("minimum_retweets") or 3)
    result_limit = int(config.get("result_limit") or 40)
    delay = max(0.0, float(config.get("request_delay_seconds") or 0.0))
    plan = build_query_plan(config)
    history = corpus.read_json(ledger.HISTORY_PATH, {})
    old_rows = history.get("candidates", []) if isinstance(history, dict) else []
    ledger_ids = {str(row.get("status_id")) for row in old_rows if isinstance(row, dict)}
    x_ids = yahoo.known_x_ids(yahoo.read_array(yahoo.X_EVENTS_PATH))
    results = []
    for index, variant in enumerate(plan):
        try:
            result = fetch_variant(
                variant,
                now=now,
                minimum_retweets=minimum_retweets,
                result_limit=result_limit,
                ledger_ids=ledger_ids,
                x_ids=x_ids,
            )
        except (RuntimeError, ValueError) as exc:
            result = {
                **{name: variant[name] for name in ("key", "label", "kind", "query")},
                "status": "failed",
                "reason": str(exc),
                "candidate_count": 0,
                "content_accepted_count": 0,
                "production_accepted_count": 0,
            }
        results.append(result)
        print(
            f"{result['key']}: {result['status']} candidates={result.get('candidate_count', 0)} "
            f"content={result.get('content_accepted_count', 0)} "
            f"production={result.get('production_accepted_count', 0)}"
        )
        if delay and index + 1 < len(plan):
            time.sleep(delay)
    comparison = enrich(results, str(config["full_variant_key"]))
    successful = sum(row.get("status") == "ok" for row in results)
    payload = {
        "schema_version": "1.0",
        "generated_at": yahoo.utc_text(now),
        "classifier_version": yahoo.PARSER_VERSION,
        "status": "ok" if successful == len(results) else ("degraded" if successful else "failed"),
        "variant_count": len(results),
        "successful_variant_count": successful,
        "failed_variant_count": len(results) - successful,
        "existing_ledger_candidate_count": len(ledger_ids),
        "existing_x_source_count": len(x_ids),
        "full_variant_key": config["full_variant_key"],
        "experiment_design": {
            "same_execution_time": True,
            "same_result_limit": result_limit,
            "same_classifier": True,
            "minimum_retweets": minimum_retweets,
            "content_precision_ignores_x_source_deduplication": True,
            "production_precision_applies_x_source_deduplication": True,
        },
        "variants": [{key: value for key, value in row.items() if key not in _PRIVATE_FIELDS} for row in results],
        **comparison,
        "limitations": [
            "Yahoo realtime ranking is time-dependent.",
            "Result-limit conditions estimate top-K precision, not corpus recall.",
            "Removing the platform block intentionally permits non-VRChat results.",
        ],
    }
    yahoo.write_json(PUBLIC_PATH, payload)
    yahoo.write_json(
        RAW_PATH,
        {
            "schema_version": "1.0",
            "generated_at": payload["generated_at"],
            "classifier_version": payload["classifier_version"],
            "variants": [
                {
                    "key": row["key"],
                    "query": row["query"],
                    "candidate_status_ids": row.get("candidate_status_ids", []),
                    "content_accepted_status_ids": row.get("content_accepted_status_ids", []),
                    "production_accepted_status_ids": row.get("production_accepted_status_ids", []),
                }
                for row in results
            ],
        },
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    payload = run(args.config)
    print(
        f"Yahoo query ablation: {payload['status']} "
        f"{payload['successful_variant_count']}/{payload['variant_count']}"
    )
    if args.require_complete and payload["successful_variant_count"] != payload["variant_count"]:
        return 1
    return 0 if payload["successful_variant_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
