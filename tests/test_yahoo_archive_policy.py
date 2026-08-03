from datetime import UTC, datetime

from scripts.collect_yahoo_corpus import configure_classifier
from scripts.reclassify_yahoo_archive import reclassify


def row(text: str, *, retweets: int = 0, status_id: str = "2080000000000000000"):
    return {
        "status_id": status_id,
        "url": f"https://x.com/host/status/{status_id}",
        "text": text,
        "author": "host",
        "retweet_count": retweets,
        "first_seen_at": "2026-08-01T00:00:00Z",
        "last_seen_at": "2026-08-02T00:00:00Z",
    }


def test_low_retweet_future_event_is_accepted():
    configure_classifier()
    accepted, rejected, evaluated = reclassify(
        [row("2026/8/7 22:00 VRChatイベント開催。参加方法はGroup+へJOIN")],
        actual_now=datetime(2026, 8, 3, tzinfo=UTC),
        x_ids=set(),
    )
    assert len(accepted) == 1
    assert rejected == []
    assert accepted[0]["retweet_count"] == 0
    assert accepted[0]["temporal_status"] == "upcoming"
    assert accepted[0]["is_archived"] is False
    assert evaluated[0]["last_decision"] == "accepted"


def test_past_event_is_accepted_and_archived():
    configure_classifier()
    accepted, rejected, _ = reclassify(
        [row("2026/7/20 22:00 VRC交流イベント開催。参加方法はJOIN", retweets=1)],
        actual_now=datetime(2026, 8, 3, tzinfo=UTC),
        x_ids=set(),
    )
    assert len(accepted) == 1
    assert rejected == []
    assert accepted[0]["temporal_status"] == "past"
    assert accepted[0]["is_archived"] is True
    assert "終了済み" in accepted[0]["tags"]


def test_missing_retweet_count_remains_fail_closed():
    configure_classifier()
    candidate = row("2026/8/7 22:00 VRChatイベント開催。参加方法はJOIN")
    candidate["retweet_count"] = None
    accepted, rejected, _ = reclassify(
        [candidate], actual_now=datetime(2026, 8, 3, tzinfo=UTC), x_ids=set()
    )
    assert accepted == []
    assert rejected[0]["reason"] == "retweet_count_missing"


def test_giveaway_only_remains_rejected():
    configure_classifier()
    accepted, rejected, _ = reclassify(
        [row("2026/8/7 22:00 VRChat向け商品プレゼント。フォロー＆RPで抽選応募", retweets=20)],
        actual_now=datetime(2026, 8, 3, tzinfo=UTC),
        x_ids=set(),
    )
    assert accepted == []
    assert rejected[0]["reason"] == "giveaway_only"


def test_missing_datetime_remains_rejected():
    configure_classifier()
    accepted, rejected, _ = reclassify(
        [row("VRChat交流イベント開催。参加方法はGroup+へJOIN", retweets=5)],
        actual_now=datetime(2026, 8, 3, tzinfo=UTC),
        x_ids=set(),
    )
    assert accepted == []
    assert rejected[0]["reason"] == "missing_datetime"
