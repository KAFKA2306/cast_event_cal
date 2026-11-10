"""Permission checks must precede network access and preserve the source."""
import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.yahoo_collection_permission import permission_status, require_permission


NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def record(tmp_path, *, approved=False, **updates):
    payload = {
        "approved": approved,
        "authority": "LINE Yahoo",
        "authorization_reference": "https://example.org/formal-written-authorization",
        "allowed_endpoint": "https://search.yahoo.co.jp/realtime/search",
        "allowed_activities": ["automated_collection", "public_redistribution"],
        "valid_until": (NOW + timedelta(days=1)).isoformat(),
    }
    payload.update(updates)
    path = tmp_path / "permission.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_missing_and_default_disabled_do_not_grant_permission(tmp_path):
    assert not permission_status(policy_path=tmp_path / "missing.json", now=NOW)[0]
    assert permission_status(policy_path=record(tmp_path), now=NOW) == (False, "permission_unverified")


@pytest.mark.parametrize("update", [
    {"authorization_reference": None},
    {"allowed_activities": ["automated_collection"]},
    {"allowed_endpoint": "https://evil.example/realtime/search"},
    {"valid_until": "2026-11-01T00:00:00Z"},
    {"valid_until": "2026-11-12T00:00:00"},
])
def test_invalid_or_expired_approval_cannot_activate_collection(tmp_path, update):
    assert not permission_status(policy_path=record(tmp_path, approved=True, **update), now=NOW)[0]


def test_complete_authorization_record_can_enable_allowed_scope(tmp_path):
    assert permission_status(policy_path=record(tmp_path, approved=True), now=NOW)[0]


def test_live_network_entrypoint_fails_closed(monkeypatch):
    import scripts.fetch_yahoo_realtime as yahoo

    class NoNetwork:
        def __init__(self, **kwargs):
            raise AssertionError("network must not be opened without authorization")

    monkeypatch.setattr(yahoo.httpx, "Client", NoNetwork)
    with pytest.raises(PermissionError, match="Yahoo automated collection disabled"):
        yahoo.fetch_page("https://search.yahoo.co.jp/realtime/search?p=VRChat")
    with pytest.raises(PermissionError, match="outside approved scope"):
        require_permission("https://other.example/realtime/search")


def test_collection_skips_network_without_erasing_existing_events(monkeypatch):
    import scripts.collect_yahoo_corpus as corpus
    import scripts.fetch_yahoo_realtime as impl

    writes = {}
    monkeypatch.setattr(corpus, "permission_status", lambda: (False, "permission_unverified"))
    monkeypatch.setattr(corpus.ledger, "read_object", lambda path: {"history_accepted_count": 2})
    monkeypatch.setattr(impl, "read_array", lambda path: [{"source_id": "existing"}])
    monkeypatch.setattr(impl, "write_json", lambda path, payload: writes.update({str(path): payload}))
    monkeypatch.setattr(corpus, "fetch_candidates", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")))

    assert corpus.main(["--mode", "daily"]) == 0
    health = writes[str(impl.HEALTH_PATH)]
    assert health["status"] == "skipped"
    assert health["queries_succeeded"] == 0
    assert health["event_count"] == 1
    assert health["history_accepted_count"] == 2
