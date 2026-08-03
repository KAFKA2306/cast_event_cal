from scripts.enrich_official_assets import (
    assets_from_payload,
    enrich_event,
    external_website,
    parse_x_identity,
    webp_image_url,
)


def test_parse_x_identity_from_status_url() -> None:
    assert parse_x_identity({"url": "https://x.com/example_name/status/1234567890"}) == ("example_name", "1234567890")


def test_webp_image_url_normalizes_x_media() -> None:
    assert webp_image_url("https://pbs.twimg.com/media/ABC123.jpg") == "https://pbs.twimg.com/media/ABC123.jpg?format=webp&name=small"


def test_profile_image_is_normalized_to_webp() -> None:
    assert webp_image_url("https://pbs.twimg.com/profile_images/1/avatar_normal.jpg", profile=True) == "https://pbs.twimg.com/profile_images/1/avatar.jpg?format=webp&name=200x200"


def test_external_website_excludes_social_and_shorteners() -> None:
    payload = {
        "user": {
            "entities": {
                "url": {
                    "urls": [
                        {"expanded_url": "https://x.com/example"},
                        {"expanded_url": "https://example.jp/events"},
                    ]
                }
            }
        }
    }
    assert external_website(payload) == "https://example.jp/events"


def test_assets_prefer_post_media_then_profile() -> None:
    payload = {
        "mediaDetails": [{"media_url_https": "https://pbs.twimg.com/media/POST.jpg"}],
        "user": {"profile_image_url_https": "https://pbs.twimg.com/profile_images/1/avatar_normal.jpg"},
    }
    result = assets_from_payload(payload, "official")
    assert result["official_x_url"] == "https://x.com/official"
    assert result["image_kind"] == "post_media"
    assert result["image_url"].endswith("format=webp&name=small")


def test_enrich_event_builds_traceable_links() -> None:
    event = {
        "url": "https://x.com/official/status/123",
        "organizer": "@official",
        "official_links": [],
    }
    cached = {
        "official_x_url": "https://x.com/official",
        "official_website_url": "https://official.example/events",
        "image_url": "https://pbs.twimg.com/media/POST.jpg?format=webp&name=small",
        "image_kind": "post_media",
        "evidence": "x_syndication",
    }
    result = enrich_event(event, cached)
    assert [row["kind"] for row in result["official_links"]] == ["announcement", "official_x", "official_web"]
    assert result["image_url"].endswith("format=webp&name=small")
    assert result["asset_enrichment"]["status"] == "enriched"
