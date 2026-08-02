from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
OUTPUT_PATH = Path("public/yahoo-recovery-pattern-audit.json")
TARGET_REASONS = {"missing_datetime", "missing_event_marker", "past_event_now"}


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("：", ":").replace("／", "/")


def datetime_signals(text: str) -> list[str]:
    value = normalized(text)
    checks = {
        "full_date_time": r"(?:20\d{2}[./年-])?\d{1,2}[./月-]\d{1,2}日?.{0,50}?(?:[01]?\d|2[0-3])(?:[:時]\d{0,2}|時半)",
        "date_only": r"(?:20\d{2}[./年-])?\d{1,2}[./月-]\d{1,2}日?",
        "weekday_time": r"(?:今週|来週|次の)?\s*[月火水木金土日]曜(?:日)?.{0,50}?(?:[01]?\d|2[0-3])(?:[:時]\d{0,2}|時半)",
        "weekday_only": r"(?:今週|来週|次の)?\s*[月火水木金土日]曜(?:日)?",
        "relative_time": r"(?:本日|今日|今夜|明日|明後日|今週末|週末).{0,50}?(?:[01]?\d|2[0-3])(?:[:時]\d{0,2}|時半)",
        "relative_only": r"(?:本日|今日|今夜|明日|明後日|今週末|週末)",
        "clock_only": r"(?:[01]?\d|2[0-3])(?:[:時]\d{0,2}|時半)",
        "recurring_weekday": r"毎週\s*[月火水木金土日]曜(?:日)?",
        "date_range": r"\d{1,2}[./月-]\d{1,2}日?\s*[-~〜～]\s*\d{1,2}[./月-]?\d{1,2}日?",
        "image_reference": r"(?:画像|フライヤー|ポスター|告知画像|詳細は画像)",
    }
    return [key for key, pattern in checks.items() if re.search(pattern, value, re.IGNORECASE | re.DOTALL)]


def structure_signals(text: str) -> list[str]:
    value = normalized(text).casefold()
    terms = {
        "vrchat": ["vrchat", "#vrc", " vrc"],
        "date_or_time": ["本日", "今日", "今夜", "明日", "月", "日", ":", "時"],
        "event_hashtag": ["#vrcイベント", "#vrchatイベント", "#vrc_event", "#vrchatevent"],
        "entry": ["join", "ジョイン", "リクイン", "reqin", "group+", "group instance", "グループインスタンス", "フレンドインスタンス", "インスタンスへ"],
        "attendance": ["遊びに来て", "遊びにきて", "お越し", "ご来場", "ご参加", "お待ちして", "入場"],
        "action": ["開催", "open", "オープン", "開場", "開始", "営業", "実施", "開演"],
        "schedule": ["予定", "スケジュール", "日時", "日程", "毎週", "定期"],
        "title_like": ["【", "[", "『", "「"],
        "broadcast": ["配信予定", "コラボ配信", "ライブ配信", "youtube", "配信枠"],
        "world_description": ["ワールド紹介", "ワールドを更新", "常設", "いつでも", "公開しました"],
    }
    return [key for key, values in terms.items() if any(term.casefold() in value for term in values)]


def top_examples(rows: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: int(row.get("max_retweet_count") or row.get("retweet_count") or 0),
        reverse=True,
    )
    return [
        {
            "status_id": row.get("status_id"),
            "retweet_count": int(row.get("max_retweet_count") or row.get("retweet_count") or 0),
            "source_created_at": row.get("source_created_at"),
            "url": row.get("url"),
            "text": str(row.get("text") or "")[:600],
            "datetime_signals": datetime_signals(str(row.get("text") or "")),
            "structure_signals": structure_signals(str(row.get("text") or "")),
        }
        for row in ordered[:limit]
    ]


def main() -> int:
    payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    candidates = [row for row in payload.get("candidates", []) if isinstance(row, dict)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        reason = str(row.get("last_reason") or "")
        if reason in TARGET_REASONS:
            grouped[reason].append(row)

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "candidate_count": len(candidates),
        "reasons": {},
    }
    for reason in sorted(TARGET_REASONS):
        rows = grouped.get(reason, [])
        dt_counts: Counter[str] = Counter()
        structure_counts: Counter[str] = Counter()
        combinations: Counter[str] = Counter()
        for row in rows:
            dt = datetime_signals(str(row.get("text") or ""))
            st = structure_signals(str(row.get("text") or ""))
            dt_counts.update(dt or ["none"])
            structure_counts.update(st or ["none"])
            combinations["+".join(sorted(st)) or "none"] += 1
        result["reasons"][reason] = {
            "count": len(rows),
            "datetime_signal_counts": dict(dt_counts.most_common()),
            "structure_signal_counts": dict(structure_counts.most_common()),
            "top_structure_combinations": dict(combinations.most_common(20)),
            "examples": top_examples(rows),
        }

    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
