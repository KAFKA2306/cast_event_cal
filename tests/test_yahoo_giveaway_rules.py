from datetime import UTC, datetime

from scripts.collect_yahoo_corpus import configure_classifier
from scripts.refine_yahoo_corpus import reevaluate_with_source_time


def row(status_id: str, text: str) -> dict[str, object]:
    return {
        "status_id": status_id,
        "url": f"https://x.com/host/status/{status_id}",
        "text": text,
        "author": "host",
        "retweet_count": 10,
        "first_seen_at": "2026-08-02T07:00:00Z",
        "last_seen_at": "2026-08-02T07:00:00Z",
        "last_decision": "pending",
        "last_reason": None,
    }


def classify(text: str, status_id: str) -> tuple[list[dict], list[dict]]:
    configure_classifier()
    accepted, rejected, _ = reevaluate_with_source_time(
        [row(status_id, text)],
        actual_now=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    return accepted, rejected


def test_product_giveaway_with_social_entry_is_not_an_event():
    accepted, rejected = classify(
        "VRC3Dモデルのピアスを抽選で3名様にプレゼント。参加方法はこのツイートをRTとフォロー。応募締切8月4日23:59",
        "2083398056188518660",
    )
    assert accepted == []
    assert rejected[0]["reason"] == "giveaway_only"


def test_booth_gift_for_friends_is_not_an_event():
    accepted, rejected = classify(
        "抽選で1名にBoothのお好きな商品をギフトします。VRCフレンドかつFFが参加条件。締切8/4 23:59",
        "2083153426167578665",
    )
    assert accepted == []
    assert rejected[0]["reason"] == "giveaway_only"


def test_event_with_priority_invite_giveaway_is_kept():
    accepted, rejected = classify(
        "#個室闇鍋VRC 開催決定。8/5 22:10からグループインスタンス先着順で参加。フォローとRPで優先招待をプレゼント",
        "2082990245176586249",
    )
    assert rejected == []
    assert accepted[0]["starts_at"] == "2026-08-05T13:10:00Z"


def test_lottery_access_event_is_kept():
    accepted, rejected = classify(
        "VRCイベント 0属オークション 第4回 8/15 22:00。リクイン抽選式、参加条件あり",
        "2083770096582119685",
    )
    assert rejected == []
    assert accepted[0]["starts_at"] == "2026-08-15T13:00:00Z"
