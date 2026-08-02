from datetime import UTC, datetime

from scripts.collect_yahoo_corpus import (
    build_query_plan,
    configure_classifier,
    read_json,
    refined_candidate_to_event,
)


def candidate(text: str, *, retweets: int = 10) -> dict[str, object]:
    return {
        "status_id": "2084000000000000000",
        "url": "https://x.com/host/status/2084000000000000000",
        "text": text,
        "author": "host",
        "retweet_count": retweets,
    }


def classify(text: str, *, retweets: int = 10, now: datetime | None = None):
    configure_classifier()
    return refined_candidate_to_event(
        candidate(text, retweets=retweets),
        now=now or datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )


def test_positive_feedback_terms_are_used_in_query_plan():
    config = read_json(__import__("pathlib").Path("config/yahoo_query_terms.json"), {})
    plan = build_query_plan(config)
    queries = "\n".join(row["query"] for row in plan)
    assert "イベント告知" in queries
    assert "通常営業" in queries
    assert "Group+ instance" in queries
    assert "朗読ミュージカル" in queries
    assert "(本日) (VRChat OR VRC)" in queries


def test_explicit_performance_type_is_accepted():
    event, reason = classify(
        "8月19日22:30 VRChatで朗読ミュージカルを上演します。ご来場をお待ちしております"
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-19T13:30:00Z"


def test_weekday_time_and_group_access_are_accepted():
    event, reason = classify(
        "日曜日のTo MeはVRC公式Groupに加入して20:50になったら第1インスタンスへJOIN。遊びに来てください",
        now=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-02T11:50:00Z"


def test_world_description_without_event_structure_is_rejected():
    event, reason = classify(
        "VRChatの映画ポスター常設ワールドを更新しました。いつでも遊びに来てください。8/19 22:00"
    )
    assert event is None
    assert reason == "missing_event_marker"


def test_product_giveaway_with_participation_word_is_rejected():
    event, reason = classify(
        "8/4 23:59 VRChat向け衣装を抽選でプレゼント。参加方法はフォローとRP"
    )
    assert event is None
    assert reason == "giveaway_only"


def test_retweet_threshold_remains_hard_gate():
    event, reason = classify(
        "8/19 22:30 VRChat朗読会を開催。Group+インスタンスへJOIN",
        retweets=2,
    )
    assert event is None
    assert reason == "retweet_below_threshold"


def test_specific_recruitment_deadline_is_kept():
    event, reason = classify(
        "VRChat店舗のキャスト募集。応募期限8/19 22:30、面接はGroupインスタンスで実施"
    )
    assert reason is None
    assert event is not None
    assert event["category"] == "recruitment_deadline"



def test_generic_vrc_event_with_attendance_language_is_accepted():
    event, reason = classify(
        "8/14 22:00 VRCイベント Dark Five Clubに出演します。是非お越しください"
    )
    assert reason is None
    assert event is not None


def test_vrchat_live_with_opening_time_is_accepted():
    event, reason = classify(
        "VRChatライブ Lumina Performance Live 8/6 22:15開場 22:30開演、Group開催"
    )
    assert reason is None
    assert event is not None


def test_training_session_with_fullwidth_group_plus_is_accepted():
    event, reason = classify(
        "VRCバドミントン部初心者講習会 8/8 22:00開催。集合場所はグループ＋"
    )
    assert reason is None
    assert event is not None


def test_streaming_schedule_without_vrchat_entry_is_rejected():
    event, reason = classify(
        "2026/8/8 22:00 VRChatコラボ配信予定。謎解きを配信します。YouTubeで見てね"
    )
    assert event is None
    assert reason == "missing_event_marker"
