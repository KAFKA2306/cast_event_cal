from datetime import UTC, datetime

from scripts import fetch_yahoo_realtime as implementation
from scripts.run_yahoo_realtime import configure


def test_vrc_marker_before_japanese_text_is_detected():
    configure()
    for text in (
        "VRCイベント 8/15 22:00 開催",
        "VRC初心者歓迎 本日22:30営業",
        "今後はVRCでも集会を開催します",
        "#VRC_EDU 8/4 21:00 開催",
    ):
        assert implementation.VRCHAT_RE.search(text), text


def test_latin_word_continuation_is_not_misdetected():
    configure()
    assert implementation.VRCHAT_RE.search("VRCイベント")
    assert implementation.VRCHAT_RE.search("VRC2年")
    assert implementation.VRCHAT_RE.search("#VRC_EDU")
    assert implementation.VRCHAT_RE.search("VRChatイベント")
    assert implementation.VRCHAT_RE.search("VRCSDK") is None


def test_explicit_vrc_event_can_pass_mechanical_gate():
    configure()
    candidate = {
        "status_id": "2083770096582119685",
        "url": "https://x.com/0zoku_vrc/status/2083770096582119685",
        "text": "VRCイベント 〜０属オークション〜 8/15 22:00～ リクイン抽選式 参加条件あり",
        "author": "0zoku_vrc",
        "retweet_count": 5,
    }
    event, reason = implementation.candidate_to_event(
        candidate,
        now=datetime(2026, 8, 2, 6, 40, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-15T13:00:00Z"
