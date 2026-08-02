from pathlib import Path

path = Path("scripts/yahoo_classifier_v19.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from datetime import UTC, datetime, time, timedelta",
    "from datetime import datetime, time, timedelta",
)
old_rollover = '''def _roll_year_if_needed(value: datetime, anchor: datetime, explicit_year: bool) -> datetime | None:
    if explicit_year or value >= anchor - timedelta(days=2):
        return value
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return None
'''
new_rollover = '''def _roll_year_if_needed(value: datetime, anchor: datetime, explicit_year: bool) -> datetime | None:
    if explicit_year or value >= anchor - timedelta(days=180):
        return value
    try:
        next_year = value.replace(year=value.year + 1)
    except ValueError:
        return value
    return next_year if next_year <= anchor + timedelta(days=180) else value
'''
if old_rollover not in text:
    raise RuntimeError("year rollover policy not found")
text = text.replace(old_rollover, new_rollover, 1)
text = text.replace(
    'WORLD_DESCRIPTION_RE = re.compile(r"(?i)(?:ワールド紹介|ワールドを更新|常設ワールド|いつでも|公開しました)")\n',
    'WORLD_DESCRIPTION_RE = re.compile(r"(?i)(?:ワールド紹介|ワールドを更新|常設ワールド|いつでも|公開しました)")\n'
    'NON_EVENT_NOTICE_RE = re.compile(r"(?i)(?:障害情報|障害発生|メンテナンス|不具合|API(?:の|に)?(?:エラー|遅延)|ログイン障害|アップデート情報)")\n',
)
old = '''def structured_classify(text: str) -> tuple[str | None, str | None]:
    from scripts import collect_yahoo_corpus as legacy

    category, reason = legacy.structured_classify(text)
    if reason != "missing_event_marker":
        return category, reason

    normalized = normalize_text(text)
    if not implementation.VRCHAT_RE.search(normalized):
        return None, "not_vrchat"
    if RECAP_RE.search(normalized):
        return None, "past_event_report"
'''
new = '''def structured_classify(text: str) -> tuple[str | None, str | None]:
    from scripts import collect_yahoo_corpus as legacy

    normalized = normalize_text(text)
    if RECAP_RE.search(normalized):
        return None, "past_event_report"
    category, reason = legacy.structured_classify(normalized)
    if reason != "missing_event_marker":
        return category, reason
    if not implementation.VRCHAT_RE.search(normalized):
        return None, "not_vrchat"
'''
if old not in text:
    raise RuntimeError("structured_classify prefix not found")
text = text.replace(old, new, 1)
old_guard = '''    world_description = bool(WORLD_DESCRIPTION_RE.search(normalized))

    if has_broadcast and not has_access and not has_attendance:
'''
new_guard = '''    world_description = bool(WORLD_DESCRIPTION_RE.search(normalized))
    non_event_notice = bool(NON_EVENT_NOTICE_RE.search(normalized))

    if non_event_notice and not (has_event_hashtag or (has_generic_event and has_action)):
        return None, "missing_event_marker"
    if has_broadcast and not has_access and not has_attendance:
'''
if old_guard not in text:
    raise RuntimeError("v1.9 guard location not found")
text = text.replace(old_guard, new_guard, 1)
path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_yahoo_selection_policy.py")
test_text = test_path.read_text(encoding="utf-8")
if "test_year_end_announcement_rolls_into_next_year" not in test_text:
    test_text = test_text.rstrip() + '''


def test_year_end_announcement_rolls_into_next_year():
    event, reason = classify(
        "【VRCイベント告知】1/10 22:00 新春交流会を開催。Group+へJOIN",
        now=datetime(2026, 12, 20, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2027-01-10T13:00:00Z"
'''
    test_path.write_text(test_text, encoding="utf-8")

Path(__file__).unlink(missing_ok=True)
