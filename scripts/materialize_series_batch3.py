from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / "config" / "event_ontology.json"
TEST_PATH = ROOT / "tests" / "test_event_series_ontology.py"
EVENTS_PATH = ROOT / "public" / "events.json"
AUDIT_PATH = ROOT / "public" / "ontology-match-audit.json"
HEALTH_PATH = ROOT / "public" / "health.json"

ENTRIES = [
    {
        "canonical_id": "vrc-idle-gathering",
        "canonical_name": "VRCでボーっとする会",
        "aliases": ["VRCでボーっとする会"],
        "organizers": ["VRCでボーっとする会"],
        "required_patterns": ["ボーっと"],
        "category": "wellness",
        "subcategory": "hangout",
        "official_links": [
            {
                "label": "VRChat Group",
                "url": "https://vrc.group/BSKAI.0397",
                "kind": "vrchat_group",
            },
            {
                "label": "イベント公式X",
                "url": "https://x.com/VRC_bskai",
                "kind": "official_x",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "毎週水曜22時30分を中心に開催",
            "note": "訪問ワールド、時間変更、参加方法は最新の公式告知を優先してください。",
        },
        "introduction": "落ち着いたワールドで、参加者がそれぞれ静かにボーっと過ごすVRChat交流会です。",
        "highlights": [
            "開催回ごとに異なる落ち着いたワールドを訪れる",
            "会話を目的にせず自分のペースで休める",
            "公式Groupインスタンスから参加できる",
        ],
        "first_time_guide": "VRChat Groupへ参加し、公式Xの当日告知で訪問ワールドとGroupインスタンスを確認してください。",
        "participation_method": "VRChat Groupの最新告知に従い、指定されたGroupインスタンスへJOIN。",
        "event_format": "静かなワールドで休憩する定期交流会",
        "audience": "VRChat内で静かに休みたい人、落ち着いたワールドを訪れたい人",
        "default_location": "VRChat",
        "tags": ["休憩", "ワールド巡り", "Group参加", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": ["https://vrc.group/BSKAI.0397", "https://x.com/VRC_bskai"],
        },
    },
    {
        "canonical_id": "vrc-petting-zoo",
        "canonical_name": "VRCふれあい動物園",
        "aliases": ["VRCふれあい動物園"],
        "organizers": ["VRCふれあい動物園"],
        "required_patterns": ["ふれあい動物園"],
        "category": "community",
        "subcategory": "social",
        "official_links": [
            {
                "label": "公式イベントワールド",
                "url": "https://vrchat.com/home/launch?worldId=wrld_9a1eedbb-34ee-49cd-87da-41e321258fb6",
                "kind": "official_website",
            },
            {
                "label": "イベント公式X",
                "url": "https://x.com/VRC_Petting_zoo",
                "kind": "official_x",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "毎週金曜22時を中心に開園",
            "note": "終了時刻、休園、参加方法は最新の公式告知を優先してください。",
        },
        "introduction": "専用ワールド内の複数エリアで、参加者が動物役のスタッフとの交流を楽しむVRChatイベントです。",
        "highlights": [
            "公式イベント用ワールドで開催される",
            "園内の複数エリアを巡って交流できる",
            "毎週金曜夜の定期イベントとして案内されている",
        ],
        "first_time_guide": "公式Xで当日の開園案内を確認し、案内されたGroupインスタンスへ参加してください。",
        "participation_method": "公式告知に従ってVRChat Groupへ参加し、指定インスタンスへJOIN。",
        "event_format": "専用ワールドを使った動物園型交流イベント",
        "audience": "動物をテーマにした交流を楽しみたい人、落ち着いて園内を巡りたい人",
        "default_location": "VRChat",
        "tags": ["動物園", "交流", "専用ワールド", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": [
                "https://vrchat.com/home/launch?worldId=wrld_9a1eedbb-34ee-49cd-87da-41e321258fb6",
                "https://x.com/VRC_Petting_zoo",
            ],
        },
    },
]

TEST_MARKER = "def test_third_verified_series_batch_matches_deterministically()"
TEST_CASE = '''


def test_third_verified_series_batch_matches_deterministically() -> None:
    entries = load_ontology()["entries"]
    entries_by_id = {entry["canonical_id"]: entry for entry in entries}
    cases = [
        ("VRCでボーっとする会", "VRCでボーっとする会", "vrc-idle-gathering"),
        ("VRCふれあい動物園", "VRCふれあい動物園", "vrc-petting-zoo"),
    ]
    assert {expected_id for _, _, expected_id in cases} <= entries_by_id.keys()
    assert entries_by_id["vrc-idle-gathering"]["category"] == "wellness"
    assert entries_by_id["vrc-petting-zoo"]["category"] == "community"

    for title, organizer, expected_id in cases:
        entry, status, evidence = select_entry(
            {"title": title, "description": "", "organizer": organizer},
            entries,
        )
        assert status == "matched"
        assert entry is not None
        assert entry["canonical_id"] == expected_id
        assert "alias" in evidence
'''

EXPECTED_SERIES = {"vrc-idle-gathering": 17, "vrc-petting-zoo": 17}


def materialize() -> None:
    ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    existing = {entry["canonical_id"] for entry in ontology["entries"]}
    ontology["entries"].extend(entry for entry in ENTRIES if entry["canonical_id"] not in existing)
    ONTOLOGY_PATH.write_text(
        json.dumps(ontology, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    tests = TEST_PATH.read_text(encoding="utf-8")
    if TEST_MARKER not in tests:
        tests += TEST_CASE
    TEST_PATH.write_text(tests, encoding="utf-8")


def validate() -> None:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    ontology = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    health = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    profiles = [row for row in events["events"] if row.get("series_profile")]

    assert events["count"] == 595
    assert len(ontology["entries"]) == 15
    assert audit["ontology_entries"] == 15
    assert audit["matched_events"] == 276
    assert audit["unmatched_events"] == 319
    assert audit["ambiguous_events"] == 0
    assert all(audit["matched_series"].get(key) == count for key, count in EXPECTED_SERIES.items())
    assert health["ontology"]["entries"] == 15
    assert health["ontology"]["matched_events"] == 276
    assert health["ontology"]["matched_series"] == 14
    assert health["ontology"]["unmatched_events"] == 319
    assert health["ontology"]["ambiguous_events"] == 0
    assert len(profiles) == 276
    assert all(
        row.get("series_profile", {}).get("curation", {}).get("status") == "human_curated"
        for row in profiles
    )
    print(
        json.dumps(
            {
                "event_count": 595,
                "ontology_entries": 15,
                "matched_events": 276,
                "unmatched_events": 319,
                "ambiguous_events": 0,
                "new_series": EXPECTED_SERIES,
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    validate() if args.validate else materialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
