import json
from pathlib import Path

from cast_event_cal.ontology import enrich_event, validate_ontology


ROOT = Path(__file__).resolve().parents[1]


def load_ontology() -> dict:
    return json.loads((ROOT / "config" / "event_ontology.json").read_text(encoding="utf-8"))


def test_series_ontology_is_human_curated_and_valid() -> None:
    ontology = load_ontology()
    validate_ontology(ontology)
    governance = ontology["governance"]
    assert governance["curation_mode"] == "human_only"
    assert governance["automatic_entry_creation"] is False
    assert governance["automatic_entry_rewrite"] is False
    assert governance["observed_events_may_only_link_to_existing_entries"] is True


def test_curated_entries_have_stable_profile_fields() -> None:
    ontology = load_ontology()
    assert ontology["schema_version"] == "2.0"
    for entry in ontology["entries"]:
        assert entry["schedule"]["type"] in {"recurring", "irregular", "one_off"}
        assert entry["schedule"]["label"]
        assert entry["schedule"]["cadence"]
        assert entry["introduction"]
        assert entry["highlights"]
        assert entry["first_time_guide"]
        assert entry["curation"]["status"] == "human_curated"
        assert entry["curation"]["reviewed_at"]
        assert all(url.startswith("https://") for url in entry["curation"]["sources"])


def test_matched_event_receives_series_profile_and_keeps_announcement_first() -> None:
    entry = load_ontology()["entries"][1]
    event = {
        "id": "example",
        "title": "Cafe & Bar FOR LIGHT 営業告知",
        "description": "本日の営業案内",
        "organizer": "@FOR_LIGHT202209",
        "url": "https://example.com/current-announcement",
        "tags": ["VRChat"],
    }
    enriched = enrich_event(event, entry)
    assert enriched["ontology_id"] == "cafe-bar-for-light"
    assert enriched["series_profile"]["schedule"]["type"] == "recurring"
    assert enriched["series_profile"]["introduction"] == entry["introduction"]
    assert enriched["series_profile"]["highlights"] == entry["highlights"]
    assert enriched["series_profile"]["first_time_guide"] == entry["first_time_guide"]
    assert enriched["official_links"][0]["kind"] == "announcement"
    assert enriched["official_links"][0]["url"] == event["url"]
    assert any(link["kind"] == "official_x" for link in enriched["official_links"])
    assert "定期開催" in enriched["tags"]
