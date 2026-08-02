from datetime import UTC, datetime

from scripts.collect_yahoo_corpus import configure_classifier
from scripts.refine_yahoo_corpus import (
    TWITTER_EPOCH_MS,
    reevaluate_with_source_time,
    twitter_snowflake_created_at,
)


def snowflake(value: datetime) -> str:
    milliseconds = int(value.timestamp() * 1000)
    return str((milliseconds - TWITTER_EPOCH_MS) << 22)


def history_row(status_id: str, text: str) -> dict[str, object]:
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


def test_twitter_snowflake_decodes_source_creation_time():
    created = twitter_snowflake_created_at("2081995073290666478")
    assert created is not None
    assert created.isoformat(timespec="milliseconds") == "2026-07-28T06:48:01.727+00:00"


def test_old_relative_announcement_is_rejected_against_current_time():
    configure_classifier()
    status_id = snowflake(datetime(2026, 7, 28, 6, 48, tzinfo=UTC))
    accepted, rejected, evaluated = reevaluate_with_source_time(
        [
            history_row(
                status_id,
                "本日21:00 VRC茶道イベントを開催。参加方法はグループインスタンスへJOIN",
            )
        ],
        actual_now=datetime(2026, 8, 2, 7, 50, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert accepted == []
    assert rejected[0]["reason"] == "past_event_now"
    assert evaluated[0]["source_created_at"].startswith("2026-07-28T06:48:00")


def test_current_relative_announcement_uses_post_day_and_is_accepted():
    configure_classifier()
    status_id = snowflake(datetime(2026, 8, 2, 6, 0, tzinfo=UTC))
    accepted, rejected, evaluated = reevaluate_with_source_time(
        [
            history_row(
                status_id,
                "本日22:00 VRChatイベントを開催。参加方法はGroup+インスタンスへJOIN",
            )
        ],
        actual_now=datetime(2026, 8, 2, 7, 0, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )
    assert rejected == []
    assert accepted[0]["starts_at"] == "2026-08-02T13:00:00Z"
    assert evaluated[0]["last_decision"] == "accepted"
