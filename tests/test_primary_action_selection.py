from scripts.discover_event_links import classify, select_primary_action


def test_vrc_group_short_url_is_a_vrchat_group() -> None:
    assert classify("https://vrc.group/ENJPLE.4029")[0] == "vrchat_group"


def test_primary_action_priority_is_deterministic() -> None:
    links = [
        {"kind": "official_web", "url": "https://example.com/event"},
        {"kind": "announcement", "url": "https://x.com/example/status/1"},
        {"kind": "vrchat_group", "url": "https://vrc.group/ENJPLE.4029"},
        {"kind": "application", "url": "https://forms.gle/example"},
    ]
    assert select_primary_action(links) == ("https://forms.gle/example", "application")


def test_vrchat_group_beats_announcement_and_website() -> None:
    links = [
        {"kind": "official_web", "url": "https://example.com/event"},
        {"kind": "announcement", "url": "https://x.com/example/status/1"},
        {"kind": "vrchat_group", "url": "https://vrc.group/FITBOX.0291"},
    ]
    assert select_primary_action(links) == ("https://vrc.group/FITBOX.0291", "vrchat_group")


def test_generic_source_does_not_become_primary_action() -> None:
    links = [{"kind": "related_web", "url": "https://example.com/search"}]
    assert select_primary_action(links) == (None, None)


def test_no_url_never_leaves_dangling_kind() -> None:
    assert select_primary_action([], None) == (None, None)
