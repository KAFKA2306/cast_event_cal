from pathlib import Path

path = Path("scripts/yahoo_classifier_v19.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "説明会|体験会|撮影会|ライブ|",
    "説明会|体験会|撮影会|ライブ|音楽祭|祭|",
)
text = text.replace(
    "        or (has_access and (has_generic_event or has_action or has_attendance))\n",
    "        or has_access\n",
)
if "def strong_occurrence" not in text or "def allow_inferred_datetime" not in text:
    raise RuntimeError("final v1.9 classifier safeguards are missing")
path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_yahoo_selection_policy.py")
test_text = test_path.read_text(encoding="utf-8")
addition = '''


def test_year_end_announcement_rolls_into_next_year():
    event, reason = classify(
        "【VRCイベント告知】1/10 22:00 新春交流会を開催。Group+へJOIN",
        now=datetime(2026, 12, 20, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2027-01-10T13:00:00Z"


def test_cancelled_event_is_not_recovered_from_relative_date():
    event, reason = classify(
        "今日のVRCブラック朝礼集会は延期します。Group+は開きません",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert event is None
    assert reason == "cancelled_or_postponed"


def test_personal_participation_plan_is_not_event_announcement():
    event, reason = classify(
        "今日は帰宅後にVRChat撮影会へ参加予定です。楽しみです",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert event is None
    assert reason == "past_event_report"


def test_vrc_unrelated_offline_event_is_rejected():
    event, reason = classify(
        "明日20:00から渋谷でDJ。VRCとは関係ないイベントです",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert event is None
    assert reason == "not_vrchat"


def test_rescheduled_event_with_new_occurrence_is_accepted():
    event, reason = classify(
        "VRCエラーで延期となっていたお散歩会を今夜22:00に再開催。Group+へJOIN",
        now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
'''
if "test_year_end_announcement_rolls_into_next_year" not in test_text:
    test_path.write_text(test_text.rstrip() + addition + "\n", encoding="utf-8")

Path(__file__).unlink(missing_ok=True)
