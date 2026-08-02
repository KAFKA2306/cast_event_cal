from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected text not found in {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        return
    target.write_text(text.replace(old, new), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def main() -> int:
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        "from scripts import run_yahoo_realtime as ledger\n",
        "from scripts import run_yahoo_realtime as ledger\nfrom scripts import yahoo_classifier_v19 as v19\n",
    )
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        "    event, reason = _ORIGINAL_CANDIDATE_TO_EVENT(\n",
        "    event, reason = v19.candidate_to_event(\n",
    )
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        "    implementation.PARSER_VERSION = \"1.8\"\n    implementation.classify = structured_classify\n    implementation.parse_event_datetime = parse_event_datetime_v18\n",
        "    implementation.PARSER_VERSION = v19.PARSER_VERSION\n    implementation.classify = v19.structured_classify\n    implementation.parse_event_datetime = v19.parse_event_datetime\n",
    )
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        "            elif start < actual_now - timedelta(hours=12):\n                reason = \"past_event_now\"\n",
        "",
    )
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        "            elif start < actual_now - timedelta(hours=12):\n                reason = \"past_event_now\"\n",
        "",
    )
    replace_all("scripts/refine_yahoo_corpus.py", 'implementation.PARSER_VERSION = "1.8"', 'implementation.PARSER_VERSION = "1.9"')
    replace_once(
        "scripts/fetch_yahoo_realtime.py",
        'PARSER_VERSION = "1.2"',
        'PARSER_VERSION = "1.9"',
    )
    replace_once(
        "scripts/fetch_yahoo_realtime.py",
        "    if event_at < now.astimezone(JST) - timedelta(hours=12):\n        return None, \"past_event\"\n",
        "",
    )
    replace_once(
        "scripts/fetch_yahoo_realtime.py",
        "    if not now - timedelta(days=1) <= start <= now + timedelta(days=180):\n        return False\n",
        "    if start > now + timedelta(days=180):\n        return False\n",
    )
    replace_once(
        "scripts/yahoo_classifier_v19.py",
        'clock = r"(?P<hour>[01]?\\d|2[0-9])(?:(?::|時)\\s*(?P<minute>\\d{1,2})|(?P<half>時半)|時)?"',
        'clock = r"(?P<hour>[01]?\\d|2[0-9])(?:(?::|時)\\s*(?P<minute>\\d{1,2})|(?P<half>時半)|時)"',
    )

    version_paths = [
        "config/yahoo_query_terms.json",
        "scripts/run_yahoo_best_1000.py",
        "scripts/run_yahoo_query_ablation.py",
        "tests/test_yahoo_selection_policy.py",
        "tests/test_yahoo_best_1000.py",
        "tests/test_yahoo_query_ablation.py",
        ".github/workflows/update-calendar-v2.yml",
        ".github/workflows/yahoo-best-1000.yml",
        ".github/workflows/yahoo-query-ablation.yml",
        "README.md",
    ]
    for path in version_paths:
        if Path(path).exists():
            replace_all(path, "1.8", "1.9")

    append_once(
        "tests/test_yahoo_selection_policy.py",
        "test_past_announcement_is_retained_in_v19",
        '''
def test_past_announcement_is_retained_in_v19():
    event, reason = classify(
        "【VRCイベント告知】7/30 21:00 赤髪メンズ集会を開催。Group+へJOIN",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-07-30T12:00:00Z"


def test_date_only_uses_explicit_estimated_slot():
    event, reason = classify(
        "7月31日 VRC音楽祭2026を開催。出演者募集の応募締切です",
        now=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-07-31T13:00:00Z"
    assert "日時推定" in event["tags"]
    assert event["confidence"] == 0.78


def test_relative_day_without_time_uses_estimated_slot():
    event, reason = classify(
        "本日 VRCイベントを開催します。グループインスタンスへJOIN",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-02T13:00:00Z"
    assert "日時推定" in event["tags"]


def test_fullwidth_datetime_and_half_hour_are_parsed():
    event, reason = classify(
        "ＶＲＣイベント告知 ８／１９ ２２時半開催。リクインで参加",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-19T13:30:00Z"


def test_dated_event_inside_world_announcement_is_recovered():
    event, reason = classify(
        "VRChat常設ワールドをオープン。7/31 21:00 第1回イベントを開催します",
        now=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None


def test_datetime_and_actual_entry_are_sufficient_structure():
    event, reason = classify(
        "VRChat 8/8 22:00 Group+インスタンスへJOINしてください",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None


def test_outage_notice_with_join_word_remains_rejected():
    event, reason = classify(
        "【VRChat障害情報】本日API遅延。JoinやInviteに影響があります",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert event is None
    assert reason == "missing_event_marker"


def test_recap_report_remains_rejected_even_when_past_events_are_allowed():
    event, reason = classify(
        "7/30 22:00 VRChat集会を開催しました。ご参加ありがとうございました。集合写真です",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert event is None
    assert reason in {"past_event_report", "missing_event_marker"}
''',
    )

    for path in ["tests/test_yahoo_v19_recovery_placeholder.py", "public/.gitkeep-v19"]:
        Path(path).unlink(missing_ok=True)
    Path(__file__).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
