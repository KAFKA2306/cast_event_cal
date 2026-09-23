from scripts.audit_primary_actions import audit


def test_actionable_official_link_requires_primary_action() -> None:
    report = audit([
        {
            "id": "event-1",
            "primary_action_url": None,
            "primary_action_kind": "announcement",
            "official_links": [{"kind": "vrchat_group", "url": "https://vrc.group/TEST.1234"}],
        }
    ])
    assert report["status"] == "error"
    assert report["failures"]["dangling_primary_action_kind"] == ["event-1"]
    assert report["failures"]["actionable_official_link_without_primary_action"] == ["event-1"]


def test_valid_primary_action_passes() -> None:
    report = audit([
        {
            "id": "event-1",
            "primary_action_url": "https://vrc.group/TEST.1234",
            "primary_action_kind": "vrchat_group",
            "official_links": [{"kind": "vrchat_group", "url": "https://vrc.group/TEST.1234"}],
        }
    ])
    assert report["status"] == "ok"
    assert report["failure_count"] == 0


def test_generic_source_link_does_not_become_actionable() -> None:
    report = audit([
        {
            "id": "event-1",
            "primary_action_url": None,
            "primary_action_kind": None,
            "official_links": [{"kind": "source", "url": "https://example.com/search"}],
        }
    ])
    assert report["status"] == "ok"
