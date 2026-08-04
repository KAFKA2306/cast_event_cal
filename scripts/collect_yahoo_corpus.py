from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import fetch_yahoo_realtime as implementation
from scripts import run_yahoo_realtime as ledger

JST = ZoneInfo("Asia/Tokyo")
CONFIG_PATH = Path("config/yahoo_query_terms.json")
SNAPSHOT_PATH = Path("data/yahoo_realtime_candidates.json")
AUDIT_PATH = Path("public/yahoo-classifier-audit.json")
HISTORY_TARGET = 1000
HISTORY_RETENTION_DAYS = 365
HISTORY_MAX_COUNT = 5000

PARTICIPATION_TERMS = {
    "参加方法", "参加条件", "join", "ジョイン", "リクイン", "reqin", "リクエストインバイト",
    "request invite", "招待", "フレンド申請", "フレリク", "グループインスタンス",
    "group instance", "group+", "group public", "フレンドインスタンス", "join制",
    "インスタンスへ", "インスタンスに", "インスタンスオープン",
}
VR_ACCESS_TERMS = {
    "join", "ジョイン", "リクイン", "reqin", "リクエストインバイト", "request invite",
    "フレンド申請", "フレリク", "グループインスタンス", "group instance", "group+",
    "グループ＋", "group public", "フレンドインスタンス", "join制",
    "インスタンスへ", "インスタンスに", "インスタンスオープン",
}
GENERIC_EVENT_NOUN_TERMS = {"イベント", "event"}
BROADCAST_ONLY_TERMS = {
    "配信予定", "コラボ配信", "ライブ配信", "youtube配信", "配信枠", "生配信",
}
PRIVATE_INSTANCE_TERMS = {
    "誕生日インスタンス", "birthday instance", "記念インスタンス", "インスタンスを開催",
}
SPECIFIC_EVENT_TERMS = {
    "イベント告知", "営業告知", "通常営業", "開催決定", "ホストイベント", "ホスイベ", "交流イベント",
    "集会", "交流会", "オークション", "ライブイベント", "公演", "djイベント", "vjイベント",
    "歌ステージ", "ステージ", "ワールドツアー", "ワールド巡り", "謎解き", "大会", "勉強会",
    "講演会", "講演", "セミナー", "上映会", "映画祭", "朗読会", "朗読劇",
    "朗読ミュージカル", "舞台公演", "演奏会", "音楽会", "撮影会", "展示会", "展覧会",
    "フェス", "festival", "祭り", "オフ会", "説明会", "体験会", "試写会", "フォトコン",
    "vrchatライブ", "performance live", "講習会",
}
EVENT_ACTION_TERMS = {"開催", "open", "オープン", "開場", "開始", "営業", "公演", "実施", "開演"}
ATTENDANCE_TERMS = {
    "参加したい", "参加できます", "参加ください", "ご参加ください", "来場", "ご来場",
    "ご来店", "遊びに来て", "遊びにきて", "お越し", "見に来て", "聴きに来て",
    "お待ちしております", "お待ちしてます", "入場",
}
SPECIFIC_RECRUITMENT_TERMS = {
    "キャスト募集", "スタッフ募集", "店員募集", "演者募集", "テスター募集", "参加者募集",
    "出展募集", "公募", "応募期限", "面接",
}
DEADLINE_TERMS = {"締切", "〆切", "応募期限", "までに", "応募完了"}
SOCIAL_ENTRY_TERMS = {"フォロー", "リポスト", "rp", "rt", "いいね", "リプ", "コメント", "抽選応募"}
WORLD_DESCRIPTION_TERMS = {"ワールド紹介", "ワールドを更新", "常設", "いつでも", "販売開始", "公開しました"}
GENERIC_EVENT_TERMS = {"開催", "イベント", "キャンペーン", "募集", "応募"}
AUDIT_GROUPS = {"commerce_noise", "temporal_audit"}
QUERY_CONTEXT = "(開催 OR 告知 OR 日時 OR OPEN OR オープン OR 開場 OR 開始 OR 営業 OR 本日 OR 今日 OR 明日 OR 今夜 OR 参加 OR JOIN OR リクイン OR Group+)"
NEXT_MONTH_CONFLICT_RE = re.compile(
    r"次回.{0,50}?(?P<label_month>1[0-2]|0?[1-9])月.{0,80}?"
    r"(?:日時|日程)\s*[:：]?\s*(?:20\d{2}[./年-])?"
    r"(?P<date_month>1[0-2]|0?[1-9])[./月-]",
    re.IGNORECASE | re.DOTALL,
)
_ORIGINAL_CANDIDATE_TO_EVENT = implementation.candidate_to_event
_ORIGINAL_PARSE_EVENT_DATETIME = implementation.parse_event_datetime


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def has_any(text: str, terms: set[str]) -> bool:
    folded = text.casefold()
    return any(term.casefold() in folded for term in terms)


def parse_event_datetime_v18(text: str, anchor: datetime) -> datetime | None:
    parsed = _ORIGINAL_PARSE_EVENT_DATETIME(text, anchor)
    if parsed is not None:
        return parsed
    normalized = implementation.normalize_text(text)
    clock = r"(?P<hour>[01]?\d|2[0-3])(?:[:時](?P<minute>\d{2})?)"
    match = re.search(
        rf"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?)?\s*(?P<weekday>[月火水木金土日])曜日?"
        rf".{{0,100}}?{clock}",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    target = {name: index for index, name in enumerate("月火水木金土日")}[match.group("weekday")]
    days_ahead = (target - anchor.weekday()) % 7
    prefix = match.group("prefix") or ""
    if prefix.startswith("来週"):
        days_ahead += 7
    elif prefix.startswith("次") and days_ahead == 0:
        days_ahead = 7
    day = (anchor + timedelta(days=days_ahead)).date()
    result = datetime(
        day.year,
        day.month,
        day.day,
        int(match.group("hour")),
        int(match.group("minute") or 0),
        tzinfo=JST,
    )
    if not prefix and days_ahead == 0 and result < anchor - timedelta(hours=2):
        result += timedelta(days=7)
    return result


def structured_classify(text: str) -> tuple[str | None, str | None]:
    if not implementation.VRCHAT_RE.search(text):
        return None, "not_vrchat"
    has_specific_event = has_any(text, SPECIFIC_EVENT_TERMS)
    has_generic_event = has_any(text, GENERIC_EVENT_NOUN_TERMS)
    has_action = has_any(text, EVENT_ACTION_TERMS)
    has_access = has_any(text, VR_ACCESS_TERMS)
    has_attendance = has_any(text, ATTENDANCE_TERMS)
    has_recruitment = has_any(text, SPECIFIC_RECRUITMENT_TERMS)
    has_deadline = has_any(text, DEADLINE_TERMS)
    has_product = has_any(text, implementation.PRODUCT_TERMS)
    has_giveaway = has_any(text, implementation.GIVEAWAY_TERMS)
    has_broadcast = has_any(text, BROADCAST_ONLY_TERMS)
    has_social_entry = has_any(text, SOCIAL_ENTRY_TERMS)
    looks_like_world_description = has_any(text, WORLD_DESCRIPTION_TERMS)
    event_structure = (
        has_specific_event
        or (has_generic_event and has_action)
        or (has_generic_event and has_attendance)
        or (has_action and has_access)
        or (has_access and has_attendance)
    )
    recruitment_structure = has_recruitment or (has_deadline and has_access)
    if has_broadcast and not has_access and not has_attendance:
        return None, "missing_event_marker"
    if has_giveaway and has_social_entry and not event_structure:
        return None, "giveaway_only"
    if has_giveaway and not event_structure:
        return None, "giveaway_only"
    if has_product and not event_structure and not recruitment_structure:
        return None, "product_only"
    if looks_like_world_description and not has_specific_event and not (has_action and has_access):
        return None, "missing_event_marker"
    if recruitment_structure:
        return "recruitment_deadline", None
    if event_structure:
        return "event", None
    return None, "missing_event_marker"


def query_for_group(group: str, term: str) -> str:
    if group == "recruitment":
        return f"({term}) (締切 OR 〆切 OR 応募期限 OR 面接 OR 募集) (VRChat OR VRC)"
    if group == "access":
        return f"({term}) {QUERY_CONTEXT} (VRChat OR VRC)"
    if group in AUDIT_GROUPS:
        return f"({term}) (VRChat OR VRC)"
    return f"({term}) {QUERY_CONTEXT} (VRChat OR VRC)"


def refined_candidate_to_event(
    candidate: dict[str, Any], *, now: datetime, min_retweets: int, x_ids: set[str]
) -> tuple[dict[str, Any] | None, str | None]:
    text = str(candidate.get("text") or "").strip()
    conflict = NEXT_MONTH_CONFLICT_RE.search(text)
    if conflict and int(conflict.group("label_month")) != int(conflict.group("date_month")):
        return None, "conflicting_date_context"

    has_participation = has_any(text, PARTICIPATION_TERMS)
    has_specific_event = has_any(text, SPECIFIC_EVENT_TERMS)
    has_product = has_any(text, implementation.PRODUCT_TERMS)
    has_giveaway = has_any(text, implementation.GIVEAWAY_TERMS)
    has_only_generic_event = has_any(text, GENERIC_EVENT_TERMS) and not has_specific_event

    if has_giveaway and not has_participation and not has_specific_event:
        return None, "giveaway_only"
    if has_product and has_only_generic_event and not has_participation:
        return None, "product_only"

    if has_any(text, PRIVATE_INSTANCE_TERMS) and not has_participation:
        return None, "missing_participation_method"

    event, reason = _ORIGINAL_CANDIDATE_TO_EVENT(
        candidate, now=now, min_retweets=min_retweets, x_ids=x_ids
    )
    if event and has_any(text, PRIVATE_INSTANCE_TERMS) and not has_participation:
        return None, "missing_participation_method"
    return event, reason


def configure_classifier() -> None:
    ledger.configure()
    implementation.PARSER_VERSION = "1.8"
    implementation.classify = structured_classify
    implementation.parse_event_datetime = parse_event_datetime_v18
    implementation.EVENT_TERMS = SPECIFIC_EVENT_TERMS | EVENT_ACTION_TERMS | PARTICIPATION_TERMS
    implementation.candidate_to_event = refined_candidate_to_event


def build_query_plan(config: dict[str, Any]) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(config.get("base_queries", [])):
        query = str(raw).strip()
        if query and query.casefold() not in seen:
            seen.add(query.casefold())
            plan.append({"key": f"base-{index:03d}", "group": "base", "term": query, "query": query})
    groups = config.get("term_groups", {})
    if not isinstance(groups, dict):
        raise ValueError("term_groups must be an object")
    for group, values in groups.items():
        if not isinstance(values, list):
            raise ValueError(f"term group {group} must be an array")
        for index, raw in enumerate(values):
            term = str(raw).strip()
            query = query_for_group(str(group), term)
            if not term or query.casefold() in seen:
                continue
            seen.add(query.casefold())
            key_term = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠]+", "-", term).strip("-").casefold()
            plan.append({
                "key": f"{group}-{index:03d}-{key_term[:40] or 'query'}",
                "group": str(group),
                "term": term,
                "query": query,
            })
    if len(plan) < 50:
        raise ValueError("Yahoo query plan must contain at least 50 unique queries")
    for row in plan:
        row["url"] = "https://search.yahoo.co.jp/realtime/search?" + urlencode(
            {"ei": "UTF-8", "p": row["query"], "md": "h"}
        )
    return plan


def select_daily_plan(plan: list[dict[str, str]], now: datetime, count: int) -> list[dict[str, str]]:
    base = [row for row in plan if row["group"] == "base"]
    production = [row for row in plan if row["group"] not in AUDIT_GROUPS | {"base"}]
    audit = [row for row in plan if row["group"] in AUDIT_GROUPS]
    production_count = max(1, min(max(count - 2, 1), len(production)))
    audit_count = min(2, len(audit))
    ordinal = now.astimezone(JST).date().toordinal()
    production_offset = (ordinal * production_count) % len(production)
    selected = base + (production[production_offset:] + production[:production_offset])[:production_count]
    if audit_count:
        audit_offset = (ordinal * audit_count) % len(audit)
        selected += (audit[audit_offset:] + audit[:audit_offset])[:audit_count]
    return selected


def candidate_score(row: dict[str, Any]) -> tuple[bool, int, int]:
    value = row.get("retweet_count")
    try:
        retweets = int(value) if value is not None else -1
    except (TypeError, ValueError):
        retweets = -1
    return value is not None, len(str(row.get("text") or "")), retweets


def add_candidate(
    selected: dict[str, dict[str, Any]], row: dict[str, Any], query: dict[str, str]
) -> None:
    status_id = str(row.get("status_id") or "")
    if not implementation.STATUS_ID_RE.fullmatch(status_id):
        return
    incoming = dict(row)
    incoming.update({
        "query_keys": [query["key"]],
        "query_groups": [query["group"]],
        "query_terms": [query["term"]],
    })
    current = selected.get(status_id)
    if current is None:
        selected[status_id] = incoming
        return
    richer = incoming if candidate_score(incoming) > candidate_score(current) else dict(current)
    richer["query_keys"] = sorted(set(current["query_keys"]) | {query["key"]})
    richer["query_groups"] = sorted(set(current["query_groups"]) | {query["group"]})
    richer["query_terms"] = sorted(set(current["query_terms"]) | {query["term"]})
    selected[status_id] = richer


def fetch_candidates(
    plan: list[dict[str, str]], existing_ids: set[str], target: int, stop_at_target: bool, delay: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    selected: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    raw_total = 0
    for index, query in enumerate(plan):
        started = time.monotonic()
        try:
            implementation.validate_search_url(query["url"])
            html, status, final_url = implementation.fetch_page(query["url"])
            rows = implementation.extract_candidates(html)
            raw_total += len(rows)
            for row in rows:
                add_candidate(selected, row, query)
            result = {
                "key": query["key"], "group": query["group"], "term": query["term"],
                "status": "ok", "http_status": status, "final_url": final_url,
                "html_bytes": len(html.encode()), "raw_candidates": len(rows),
                "unique_candidates_after_query": len(selected),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        except (RuntimeError, ValueError) as exc:
            result = {
                "key": query["key"], "group": query["group"], "term": query["term"],
                "status": "failed", "reason": str(exc), "raw_candidates": 0,
                "unique_candidates_after_query": len(selected),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        results.append(result)
        if stop_at_target and len(existing_ids | set(selected)) >= target:
            break
        if delay > 0 and index + 1 < len(plan):
            time.sleep(delay)
    return list(selected.values()), results, raw_total


def merge_provenance(
    merged: list[dict[str, Any]],
    existing: list[dict[str, Any]],
    observed: list[dict[str, Any]],
    observed_at: datetime,
) -> list[dict[str, Any]]:
    old = {str(row.get("status_id")): row for row in existing}
    new = {str(row.get("status_id")): row for row in observed}
    for row in merged:
        status_id = str(row["status_id"])
        previous = old.get(status_id, {})
        current = new.get(status_id, {})
        row["query_keys"] = sorted(set(previous.get("query_keys", [])) | set(current.get("query_keys", [])))
        row["query_groups"] = sorted(set(previous.get("query_groups", [])) | set(current.get("query_groups", [])))
        row["query_terms"] = sorted(set(previous.get("query_terms", [])) | set(current.get("query_terms", [])))
        row["observation_count"] = int(previous.get("observation_count") or 0) + (1 if current else 0)
        row["max_retweet_count"] = max(
            int(previous.get("max_retweet_count") or previous.get("retweet_count") or 0),
            int(current.get("retweet_count") or 0),
        )
        if previous:
            row["first_seen_at"] = previous.get("first_seen_at") or row.get("first_seen_at")
        if current:
            row["last_seen_at"] = utc_text(observed_at)
    merged.sort(
        key=lambda row: (str(row.get("last_seen_at")), str(row.get("status_id"))),
        reverse=True,
    )
    return merged[:HISTORY_MAX_COUNT]


def reevaluate(
    history: list[dict[str, Any]], actual_now: datetime, min_retweets: int, x_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accepted, rejected, evaluated = ledger.reevaluate_history(
        history, actual_now=actual_now, min_retweets=min_retweets, x_ids=x_ids
    )
    accepted_by_status = {
        str(row.get("source_id", "")).split(":")[-1]: row for row in accepted
    }
    rejected_by_status = {str(row.get("status_id")): row for row in rejected}
    final_accepted: list[dict[str, Any]] = []
    for row in evaluated:
        status_id = str(row.get("status_id"))
        event = accepted_by_status.get(status_id)
        if event:
            start = implementation.parse_instant(str(event.get("starts_at") or ""))
            reason = None
            if start is None:
                reason = "missing_datetime"
            elif start < actual_now - timedelta(hours=12):
                reason = "past_event_now"
            elif start > actual_now + timedelta(days=180):
                reason = "too_far_future_now"
            if reason:
                row["last_decision"] = "rejected"
                row["last_reason"] = reason
                rejected_by_status[status_id] = {
                    "status_id": status_id, "url": row.get("url"), "reason": reason,
                    "retweet_count": row.get("retweet_count"),
                    "first_seen_at": row.get("first_seen_at"),
                    "last_seen_at": row.get("last_seen_at"),
                    "text_excerpt": str(row.get("text") or "")[:360],
                }
            else:
                final_accepted.append(event)
    final_rejected = list(rejected_by_status.values())
    return final_accepted, final_rejected, evaluated


def audit_payload(
    before: list[dict[str, Any]], evaluated: list[dict[str, Any]],
    query_results: list[dict[str, Any]], target: int, now: datetime
) -> dict[str, Any]:
    previous = {str(row.get("status_id")): row for row in before}
    decisions = Counter(str(row.get("last_decision") or "unknown") for row in evaluated)
    reasons = Counter(str(row.get("last_reason") or "accepted") for row in evaluated)
    transitions = Counter()
    high_retweet = []
    suspicious = []
    for row in evaluated:
        status_id = str(row.get("status_id"))
        old = previous.get(status_id, {})
        transitions[
            f"{old.get('last_decision', 'new')}:{old.get('last_reason', 'none')}->"
            f"{row.get('last_decision')}:{row.get('last_reason') or 'accepted'}"
        ] += 1
        retweets = int(row.get("max_retweet_count") or row.get("retweet_count") or 0)
        if row.get("last_decision") == "rejected" and retweets >= 3:
            high_retweet.append({
                "status_id": status_id, "url": row.get("url"), "retweet_count": retweets,
                "reason": row.get("last_reason"), "text_excerpt": str(row.get("text") or "")[:360],
                "query_groups": row.get("query_groups", []),
            })
        if row.get("last_decision") == "accepted" and (
            has_any(str(row.get("text") or ""), implementation.PRODUCT_TERMS)
            or has_any(str(row.get("text") or ""), implementation.GIVEAWAY_TERMS)
        ):
            suspicious.append({
                "status_id": status_id, "url": row.get("url"),
                "text_excerpt": str(row.get("text") or "")[:360],
            })
    high_retweet.sort(key=lambda row: int(row["retweet_count"]), reverse=True)
    total = len(evaluated)
    accepted = decisions.get("accepted", 0)
    return {
        "schema_version": "1.0", "classifier_version": implementation.PARSER_VERSION,
        "generated_at": utc_text(now), "target_count": target,
        "candidate_count": total, "target_reached": total >= target,
        "accepted_count": accepted, "rejected_count": decisions.get("rejected", 0),
        "acceptance_rate": round(accepted / total, 6) if total else 0.0,
        "rejection_reason_counts": {
            key: value for key, value in sorted(reasons.items()) if key != "accepted"
        },
        "decision_transitions": dict(sorted(transitions.items())),
        "query_results": query_results,
        "high_retweet_rejections": high_retweet[:200],
        "suspicious_accepted_commerce": suspicious[:100],
        "quality": {
            "duplicate_status_ids": total - len({str(row.get("status_id")) for row in evaluated}),
            "missing_first_seen_at": sum(not row.get("first_seen_at") for row in evaluated),
            "missing_last_seen_at": sum(not row.get("last_seen_at") for row in evaluated),
            "ambiguous_decisions": sum(
                row.get("last_decision") not in {"accepted", "rejected"} for row in evaluated
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("daily", "bootstrap"), default="daily")
    parser.add_argument("--target", type=int)
    parser.add_argument("--max-queries", type=int)
    parser.add_argument("--delay-seconds", type=float)
    parser.add_argument("--require-target", action="store_true")
    args = parser.parse_args(argv)

    configure_classifier()
    config = read_json(CONFIG_PATH, {})
    if not isinstance(config, dict):
        raise ValueError("Yahoo query config must be an object")
    target = int(args.target or config.get("target_count") or HISTORY_TARGET)
    delay = float(
        args.delay_seconds if args.delay_seconds is not None
        else config.get("request_delay_seconds", 0.75)
    )
    now = datetime.now(UTC).replace(microsecond=0)
    before = ledger.read_history()
    plan = build_query_plan(config)
    if args.mode == "bootstrap":
        selected_plan = plan[: int(args.max_queries or config.get("bootstrap_query_count", 140))]
    else:
        daily_count = int(config.get("daily_query_count", 16)) * (2 if len(before) < target else 1)
        selected_plan = select_daily_plan(plan, now, int(args.max_queries or daily_count))

    observed, query_results, raw_total = fetch_candidates(
        selected_plan,
        {str(row.get("status_id")) for row in before},
        target,
        args.mode == "bootstrap",
        max(0.0, delay),
    )
    successful = sum(row.get("status") == "ok" for row in query_results)
    if successful == 0:
        health = ledger.read_object(implementation.HEALTH_PATH)
        health.update({
            "parser_version": implementation.PARSER_VERSION, "status": "degraded",
            "reason": "all Yahoo corpus queries failed; retained history and events",
            "corpus_target_count": target, "corpus_candidate_count": len(before),
            "corpus_target_reached": len(before) >= target,
            "queries_attempted": len(query_results), "queries_succeeded": 0,
            "queries_failed": len(query_results), "query_results": query_results,
        })
        implementation.write_json(implementation.HEALTH_PATH, health)
        return 1 if args.require_target and len(before) < target else 0

    implementation.write_json(SNAPSHOT_PATH, {
        "schema_version": "1.0", "generated_at": utc_text(now), "mode": args.mode,
        "candidate_count": len(observed), "raw_candidate_count": raw_total,
        "duplicate_observations_removed": max(0, raw_total - len(observed)),
        "query_results": query_results, "candidates": observed,
    })

    ledger.HISTORY_RETENTION_DAYS = int(config.get("retention_days", HISTORY_RETENTION_DAYS))
    migrated = ledger.merge_history(
        before, implementation.read_array(implementation.REJECTED_PATH),
        implementation.parse_instant(
            str(ledger.read_object(implementation.HEALTH_PATH).get("generated_at") or "")
        ) or now,
    )
    merged = ledger.merge_history(migrated, observed, now)
    merged = merge_provenance(merged, before, observed, now)
    min_retweets = int(os.environ.get("YAHOO_MIN_RETWEETS", "3"))
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, rejected, evaluated = reevaluate(merged, now, min_retweets, x_ids)
    accepted.sort(key=lambda row: (str(row.get("starts_at")), str(row.get("source_id"))))
    rejected.sort(
        key=lambda row: (-int(row.get("retweet_count") or 0), str(row.get("reason")), str(row.get("status_id")))
    )
    implementation.write_json(implementation.OUTPUT_PATH, accepted)
    implementation.write_json(implementation.REJECTED_PATH, rejected[:2000])
    implementation.write_json(ledger.HISTORY_PATH, {
        "schema_version": "2.0",
        "retention_days": ledger.HISTORY_RETENTION_DAYS,
        "maximum_candidates": int(config.get("maximum_candidates", HISTORY_MAX_COUNT)),
        "target_count": target, "target_reached": len(evaluated) >= target,
        "generated_at": utc_text(now), "candidate_count": len(evaluated),
        "query_summary": {
            "attempted": len(query_results), "succeeded": successful,
            "failed": len(query_results) - successful,
        },
        "candidates": evaluated,
    })
    audit = audit_payload(before, evaluated, query_results, target, now)
    implementation.write_json(AUDIT_PATH, audit)
    health = ledger.read_object(implementation.HEALTH_PATH)
    health.update({
        "schema_version": "2.0", "parser_version": implementation.PARSER_VERSION,
        "generated_at": utc_text(now),
        "status": "ok" if successful == len(query_results) else "degraded",
        "reason": None if successful == len(query_results) else "partial Yahoo query failure",
        "event_count": len(accepted), "history_replay_mode": "sharded_corpus",
        "history_retention_days": ledger.HISTORY_RETENTION_DAYS,
        "history_candidate_count": len(evaluated), "history_accepted_count": len(accepted),
        "history_rejected_count": len(rejected), "corpus_target_count": target,
        "corpus_target_reached": len(evaluated) >= target,
        "queries_attempted": len(query_results), "queries_succeeded": successful,
        "queries_failed": len(query_results) - successful,
        "raw_candidate_count": raw_total, "unique_candidates_this_run": len(observed),
        "duplicate_observations_removed": max(0, raw_total - len(observed)),
        "rejection_counts": audit["rejection_reason_counts"], "query_results": query_results,
    })
    implementation.write_json(implementation.HEALTH_PATH, health)
    print(
        f"Yahoo corpus: mode={args.mode} queries={len(query_results)} successful={successful} "
        f"observed={len(observed)} history={len(evaluated)} accepted={len(accepted)} "
        f"rejected={len(rejected)} target={target}"
    )
    return 2 if args.require_target and len(evaluated) < target else 0


if __name__ == "__main__":
    raise SystemExit(main())
