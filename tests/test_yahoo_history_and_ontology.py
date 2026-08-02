from datetime import UTC, datetime

from scripts.enrich_event_ontology import enrich_event, select_entry
from scripts.run_yahoo_realtime import configure, merge_history, reevaluate_history


def test_history_reprocesses_vrc_before_japanese_and_relative_date():
    configure()
    actual_now = datetime(2026, 8, 2, 7, 0, tzinfo=UTC)
    history = [
        {
            "status_id": "2083770096582119685",
            "url": "https://x.com/0zoku_vrc/status/2083770096582119685",
            "text": "VRCイベント 0属オークション 第4回 8/15 22:00～ 参加条件あり",
            "author": "0zoku_vrc",
            "retweet_count": 5,
            "first_seen_at": "2026-08-02T06:40:22Z",
            "last_seen_at": "2026-08-02T06:40:22Z",
        },
        {
            "status_id": "2083738482703466864",
            "url": "https://x.com/FOR_LIGHT202209/status/2083738482703466864",
            "text": "Cafe & Bar FOR LIGHT 本日22:30〜23:35 OPEN 参加方法 JOIN制 VRC初心者歓迎",
            "author": "FOR_LIGHT202209",
            "retweet_count": 5,
            "first_seen_at": "2026-08-02T06:40:22Z",
            "last_seen_at": "2026-08-02T06:40:22Z",
        },
    ]
    accepted, rejected, evaluated = reevaluate_history(
        history, actual_now=actual_now, min_retweets=3, x_ids=set()
    )
    assert not rejected
    assert len(evaluated) == 2
    starts = {item["source_id"]: item["starts_at"] for item in accepted}
    assert starts["yahoo:x:2083770096582119685"] == "2026-08-15T13:00:00Z"
    # "本日" is anchored to first_seen_at, not the later reprocessing day.
    assert starts["yahoo:x:2083738482703466864"] == "2026-08-02T13:30:00Z"


def test_history_preserves_first_seen_and_highest_retweet_count():
    first = datetime(2026, 8, 2, 1, 0, tzinfo=UTC)
    later = datetime(2026, 8, 3, 1, 0, tzinfo=UTC)
    existing = [
        {
            "status_id": "1234567890123456789",
            "url": "https://x.com/host/status/1234567890123456789",
            "text": "8/10 21:00 VRCイベント開催",
            "retweet_count": 8,
            "first_seen_at": "2026-08-02T01:00:00Z",
            "last_seen_at": "2026-08-02T01:00:00Z",
        }
    ]
    observed = [
        {
            "status_id": "1234567890123456789",
            "url": "https://x.com/host/status/1234567890123456789",
            "text": "8/10 21:00 VRCイベント開催",
            "retweet_count": 5,
        }
    ]
    merged = merge_history(existing, observed, later)
    assert merged[0]["first_seen_at"] == "2026-08-02T01:00:00Z"
    assert merged[0]["last_seen_at"] == "2026-08-03T01:00:00Z"
    assert merged[0]["retweet_count"] == 8


def test_ontology_enriches_only_deterministic_unique_match():
    entries = [
        {
            "canonical_id": "for-light",
            "canonical_name": "Cafe & Bar FOR LIGHT",
            "aliases": ["Cafe & Bar FOR LIGHT", "FOR LIGHT"],
            "organizers": ["@FOR_LIGHT202209"],
            "required_patterns": ["FOR LIGHT"],
            "official_links": [
                {
                    "label": "主催者公式X",
                    "url": "https://x.com/FOR_LIGHT202209",
                    "kind": "organizer_profile",
                }
            ],
            "participation_method": "JOIN制",
            "event_format": "カフェ・バー",
            "audience": "一般参加者",
            "tags": ["初心者歓迎"],
        }
    ]
    event = {
        "id": "event-1",
        "title": "Cafe & Bar FOR LIGHT",
        "organizer": "@FOR_LIGHT202209",
        "description": "本日22:30 OPEN",
        "url": "https://x.com/FOR_LIGHT202209/status/1",
        "tags": ["VRChat"],
    }
    entry, status, evidence = select_entry(event, entries)
    assert status == "matched"
    assert entry is not None
    assert {"alias", "organizer", "required_patterns"} <= set(evidence)
    enriched = enrich_event(event, entry)
    assert enriched["ontology_id"] == "for-light"
    assert enriched["participation_method"] == "JOIN制"
    assert len(enriched["official_links"]) == 2
    assert "参加方法: JOIN制" in enriched["description"]
    assert "オントロジー補完" in enriched["tags"]


def test_ontology_rejects_pattern_only_and_tied_matches():
    event = {"title": "一般オークション", "organizer": "@unknown", "description": "オークション開催"}
    pattern_only = [
        {
            "canonical_id": "one",
            "aliases": ["別イベント"],
            "organizers": ["@someone"],
            "required_patterns": ["オークション"],
        }
    ]
    assert select_entry(event, pattern_only)[1] == "unmatched"

    tied = [
        {"canonical_id": "one", "aliases": ["一般オークション"], "organizers": [], "required_patterns": []},
        {"canonical_id": "two", "aliases": ["一般オークション"], "organizers": [], "required_patterns": []},
    ]
    assert select_entry(event, tied)[1] == "ambiguous"
