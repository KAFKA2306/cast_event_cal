from scripts.validate_public_image_assets import sanitize_event_images


def test_unreachable_preferred_image_falls_back_without_removing_valid_source_image() -> None:
    events = [
        {
            "id": "evt-1",
            "preferred_image_url": "https://cdn.example/broken.webp",
            "preferred_image_kind": "vrchat_group",
            "image_url": "https://cdn.example/source.webp",
            "image_kind": "post_media",
        }
    ]

    def probe(url: str) -> tuple[bool, str]:
        if "broken" in url:
            return False, "http_404"
        return True, "ok"

    sanitized, audit = sanitize_event_images(events, probe=probe, max_workers=2)
    assert sanitized[0]["preferred_image_url"] is None
    assert sanitized[0]["preferred_image_kind"] is None
    assert sanitized[0]["image_url"] == "https://cdn.example/source.webp"
    assert sanitized[0]["image_kind"] == "post_media"
    assert audit["failed_url_count"] == 1
    assert audit["events_degraded"] == 1
    assert audit["failures"] == {"http_404": 1}


def test_duplicate_image_url_is_probed_once_and_stripped_from_all_render_fields() -> None:
    calls: list[str] = []
    events = [
        {
            "id": "evt-2",
            "preferred_image_url": "https://cdn.example/stale.webp",
            "preferred_image_kind": "organizer_profile",
            "image_url": "https://cdn.example/stale.webp",
            "image_kind": "organizer_profile",
        }
    ]

    def probe(url: str) -> tuple[bool, str]:
        calls.append(url)
        return False, "http_404"

    sanitized, audit = sanitize_event_images(events, probe=probe)
    assert calls == ["https://cdn.example/stale.webp"]
    assert sanitized[0]["preferred_image_url"] is None
    assert sanitized[0]["preferred_image_kind"] is None
    assert sanitized[0]["image_url"] is None
    assert sanitized[0]["image_kind"] is None
    assert audit["checked_url_count"] == 1
    assert audit["stripped_image_fields"] == 2


def test_reachable_image_is_preserved() -> None:
    events = [{"id": "evt-3", "image_url": "https://cdn.example/live.webp", "image_kind": "post_media"}]
    sanitized, audit = sanitize_event_images(events, probe=lambda _url: (True, "ok"))
    assert sanitized == events
    assert audit["reachable_url_count"] == 1
    assert audit["failed_url_count"] == 0
