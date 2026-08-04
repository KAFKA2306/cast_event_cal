from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / "config" / "event_ontology.json"
TEST_PATH = ROOT / "tests" / "test_event_series_ontology.py"
EVENTS_PATH = ROOT / "public" / "events.json"
AUDIT_PATH = ROOT / "public" / "ontology-match-audit.json"

ENTRIES = [
    {
        "canonical_id": "exploit-club",
        "canonical_name": "EXPLOIT部 定期対戦会",
        "aliases": ["EXPLOIT部 定期対戦会", "EXPLOIT部"],
        "organizers": ["EXPLOIT"],
        "required_patterns": ["EXPLOIT"],
        "category": "game",
        "subcategory": "tabletop",
        "official_links": [
            {
                "label": "VRChat Group",
                "url": "https://vrc.group/EXP000.2277",
                "kind": "vrchat_group",
            },
            {
                "label": "公式ワールド",
                "url": "https://vrchat.com/home/launch?worldId=wrld_32dca393-84f9-4a9b-8055-7533df73d25e",
                "kind": "official_website",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "公式Group告知に基づく定期対戦会",
            "note": "開催日時と参加方法は最新のVRChat Group告知を優先してください。",
        },
        "introduction": "VRChat向けボードゲーム「EXPLOIT」を参加者同士で遊ぶ定期対戦会です。",
        "highlights": [
            "公式のEXPLOITワールドで対戦できる",
            "VRChat Groupを参加導線として利用する",
            "継続開催のため対戦経験を積みやすい",
        ],
        "first_time_guide": "VRChat Groupへ参加し、最新告知で開催日時とインスタンスを確認してから参加してください。",
        "participation_method": "VRChat Groupの最新告知に従い、指定インスタンスへJOIN。",
        "event_format": "VRChat内ボードゲーム対戦会",
        "audience": "EXPLOITを遊びたい参加者、ルールを確認しながら参加したい人",
        "default_location": "VRChat",
        "tags": ["ボードゲーム", "EXPLOIT", "Group参加", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": [
                "https://vrc.group/EXP000.2277",
                "https://vrchat.com/home/launch?worldId=wrld_32dca393-84f9-4a9b-8055-7533df73d25e",
            ],
        },
    },
    {
        "canonical_id": "vrc-game-world-club",
        "canonical_name": "VRCゲームワールド部",
        "aliases": ["VRCゲームワールド部 月曜イベント", "VRCゲームワールド部"],
        "organizers": ["VRCゲームワールド部"],
        "required_patterns": ["ゲームワールド"],
        "category": "game",
        "subcategory": "world_tour",
        "official_links": [
            {
                "label": "VRChat Group",
                "url": "https://vrc.group/0913.3316",
                "kind": "vrchat_group",
            },
            {
                "label": "イベント公式X",
                "url": "https://x.com/VRC_GWC",
                "kind": "official_x",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "月曜夜を中心に定期開催",
            "note": "当日のゲーム、開始時刻、参加方法は公式告知を優先してください。",
        },
        "introduction": "参加者が集まり、VRChatのゲームワールドを一緒に遊ぶ定期イベントです。",
        "highlights": [
            "複数の参加者とゲームワールドを遊べる",
            "開催回ごとの案内に沿って参加できる",
            "VRChat Groupと公式Xから最新情報を確認できる",
        ],
        "first_time_guide": "VRChat Groupへ参加し、公式XまたはGroup告知で当日のゲームと参加手順を確認してください。",
        "participation_method": "VRChat Groupの告知に従い、指定されたGroupインスタンスへJOIN。",
        "event_format": "ゲームワールド交流会",
        "audience": "VRChatのゲームワールドを複数人で遊びたい人",
        "default_location": "VRChat",
        "tags": ["ゲームワールド", "交流", "Group参加", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": ["https://vrc.group/0913.3316", "https://x.com/VRC_GWC"],
        },
    },
    {
        "canonical_id": "ml-gathering",
        "canonical_name": "ML集会",
        "aliases": ["ML集会", "マシンラーニング集会"],
        "organizers": ["ML集会"],
        "required_patterns": ["ML"],
        "category": "technology",
        "subcategory": "machine_learning",
        "official_links": [
            {
                "label": "VRChat Group",
                "url": "https://vrc.group/VRCML.9230",
                "kind": "vrchat_group",
            },
            {
                "label": "イベント公式X",
                "url": "https://x.com/VRC_ML_hangout",
                "kind": "official_x",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "毎週水曜21時30分を中心に開催",
            "note": "休止、時間変更、発表企画の有無は最新の公式告知を優先してください。",
        },
        "introduction": "機械学習に関する情報共有と雑談を行うVRChat上の技術交流会です。",
        "highlights": [
            "機械学習の話題を参加者同士で共有できる",
            "技術情報と雑談の両方を扱う",
            "公式Groupと公式Xで開催情報を確認できる",
        ],
        "first_time_guide": "VRChat Groupへ参加し、公式XまたはGroup告知で開催時刻と参加インスタンスを確認してください。",
        "participation_method": "VRChat Groupの最新告知に従い、指定インスタンスへJOIN。",
        "event_format": "機械学習の情報共有・技術交流会",
        "audience": "機械学習に関心がある人、関連技術について話したい人",
        "default_location": "VRChat",
        "tags": ["機械学習", "技術交流", "情報共有", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": ["https://vrc.group/VRCML.9230", "https://x.com/VRC_ML_hangout"],
        },
    },
    {
        "canonical_id": "personally-match",
        "canonical_name": "Personally Match",
        "aliases": ["Personally match", "Personally Match"],
        "organizers": ["Personally match 開催通知"],
        "required_patterns": ["Personally"],
        "category": "community",
        "subcategory": "matching",
        "official_links": [
            {
                "label": "VRChat Group",
                "url": "https://vrc.group/PERSON.2080",
                "kind": "vrchat_group",
            },
            {
                "label": "公式ワールド",
                "url": "https://vrchat.com/home/launch?worldId=wrld_31422b22-6f53-4f9a-aed1-104128ab17d3",
                "kind": "official_website",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "毎週土曜を中心に開催",
            "note": "開催時刻と特別回の有無は最新の公式告知を優先してください。",
        },
        "introduction": "4つの性格質問への回答をもとに、同じ回答または相性のよい回答を選んだ参加者と交流するマッチングイベントです。",
        "highlights": [
            "4つの性格質問に回答して参加する",
            "回答に応じて8つの家へ分かれる",
            "同じ回答または相性のよい回答を選んだ参加者と交流できる",
        ],
        "first_time_guide": "VRChat Groupへ参加し、公式ワールドの説明と最新告知を確認してから指定インスタンスへ参加してください。",
        "participation_method": "VRChat Groupの最新告知に従い、指定インスタンスへJOIN。",
        "event_format": "性格質問を使った交流・マッチングイベント",
        "audience": "日本語で参加者との交流を楽しみたい人",
        "default_location": "VRChat",
        "tags": ["交流", "マッチング", "性格質問", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": [
                "https://vrc.group/PERSON.2080",
                "https://vrchat.com/home/launch?worldId=wrld_31422b22-6f53-4f9a-aed1-104128ab17d3",
            ],
        },
    },
    {
        "canonical_id": "vrc-beginner-world-tour",
        "canonical_name": "VRC初心者ワールドツアー",
        "aliases": ["VRC初心者ワールドツアー"],
        "organizers": ["VRC初心者ワールドツアー"],
        "required_patterns": ["初心者", "ワールドツアー"],
        "category": "beginner",
        "subcategory": "world_tour",
        "official_links": [
            {
                "label": "公式イベント案内",
                "url": "https://vrchat.com/home/group/grp_66c9286a-ad97-48dd-b21c-1b64122ac4ff/calendar/cal_2dc2fa59-470e-4bb6-b14d-7ed40b8039ee",
                "kind": "participation_guide",
            },
            {
                "label": "公式ワールド",
                "url": "https://vrchat.com/home/launch?worldId=wrld_20a3f7c6-9529-4af3-8bae-f60109a1b6ea",
                "kind": "official_website",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "公式Groupカレンダーに基づく定期開催",
            "note": "開催日時、訪問先、参加方法は最新の公式イベント案内を優先してください。",
        },
        "introduction": "VRChat初心者向けに、おすすめのワールドを参加者と一緒に巡るワールドツアーです。",
        "highlights": [
            "初心者向けのワールドを案内する",
            "複数の参加者とワールドを巡れる",
            "公式Groupカレンダーから開催情報を確認できる",
        ],
        "first_time_guide": "公式イベント案内で開催時刻と参加方法を確認し、指定されたインスタンスへ参加してください。",
        "participation_method": "公式Groupカレンダーの案内に従い、指定インスタンスへJOIN。",
        "event_format": "初心者向けワールドツアー",
        "audience": "VRChatを始めたばかりの人、初心者向けワールドを知りたい人",
        "default_location": "VRChat",
        "tags": ["初心者向け", "ワールドツアー", "Group参加", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": [
                "https://vrchat.com/home/group/grp_66c9286a-ad97-48dd-b21c-1b64122ac4ff/calendar/cal_2dc2fa59-470e-4bb6-b14d-7ed40b8039ee",
                "https://vrchat.com/home/launch?worldId=wrld_20a3f7c6-9529-4af3-8bae-f60109a1b6ea",
            ],
        },
    },
    {
        "canonical_id": "vrc-fit-boxing",
        "canonical_name": "VRCフィットボクシング集会",
        "aliases": [
            "VRCフィットボクシング集会",
            "VRCフィットボクシング集会（土曜）",
            "VRCフィットボクシング集会（日曜）",
        ],
        "organizers": ["VRCフィットボクシング集会"],
        "required_patterns": ["フィットボクシング"],
        "category": "community",
        "subcategory": "fitness",
        "official_links": [
            {
                "label": "VRChat Group",
                "url": "https://vrc.group/FITBOX.0291",
                "kind": "vrchat_group",
            },
            {
                "label": "主催者公式X",
                "url": "https://x.com/fi_sound",
                "kind": "official_x",
            },
        ],
        "schedule": {
            "type": "recurring",
            "label": "定期開催",
            "cadence": "毎週土曜・日曜21時を中心に開催",
            "note": "休止、時間変更、参加方法は最新の公式告知を優先してください。",
        },
        "introduction": "VRChat内で運動動画に合わせ、参加者が一緒に身体を動かすフィットネス集会です。",
        "highlights": [
            "参加者と同じ時間に身体を動かせる",
            "土曜・日曜の定期開催として案内されている",
            "VRChat Groupと主催者公式Xから最新情報を確認できる",
        ],
        "first_time_guide": "VRChat Groupへ参加し、主催者公式XまたはGroup告知で当日の参加方法を確認してください。",
        "participation_method": "VRChat Groupの最新告知に従い、指定インスタンスへJOIN。",
        "event_format": "運動動画に合わせる参加型フィットネス集会",
        "audience": "VRChat上で参加者と一緒に運動したい人",
        "default_location": "VRChat",
        "tags": ["フィットネス", "運動", "Group参加", "定期開催"],
        "curation": {
            "status": "human_curated",
            "reviewed_at": "2026-08-04",
            "sources": ["https://vrc.group/FITBOX.0291", "https://x.com/fi_sound"],
        },
    },
]

TEST_MARKER = "def test_second_verified_series_batch_matches_deterministically()"
TEST_CASE = '''


def test_second_verified_series_batch_matches_deterministically() -> None:
    entries = load_ontology()["entries"]
    cases = [
        ("EXPLOIT部 定期対戦会", "EXPLOIT", "exploit-club"),
        ("VRCゲームワールド部 月曜イベント", "VRCゲームワールド部", "vrc-game-world-club"),
        ("ML集会", "ML集会", "ml-gathering"),
        ("Personally match", "Personally match 開催通知", "personally-match"),
        ("VRC初心者ワールドツアー", "VRC初心者ワールドツアー", "vrc-beginner-world-tour"),
        ("VRCフィットボクシング集会（土曜）", "VRCフィットボクシング集会", "vrc-fit-boxing"),
        ("VRCフィットボクシング集会（日曜）", "VRCフィットボクシング集会", "vrc-fit-boxing"),
    ]
    expected_ids = {expected_id for _, _, expected_id in cases}
    assert expected_ids <= {entry["canonical_id"] for entry in entries}

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

EXPECTED_SERIES = {
    "exploit-club": 18,
    "vrc-game-world-club": 18,
    "ml-gathering": 17,
    "personally-match": 17,
    "vrc-beginner-world-tour": 17,
    "vrc-fit-boxing": 34,
}


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
    rows = events["events"]
    profiles = [row for row in rows if row.get("series_profile")]

    assert events["count"] == 595
    assert len(ontology["entries"]) == 13
    assert audit["ontology_entries"] == 13
    assert audit["matched_events"] == 242
    assert audit["unmatched_events"] == 353
    assert audit["ambiguous_events"] == 0
    assert all(audit["matched_series"].get(key) == count for key, count in EXPECTED_SERIES.items())
    assert len(profiles) == audit["matched_events"]
    assert all(
        row.get("series_profile", {}).get("curation", {}).get("status") == "human_curated"
        for row in profiles
    )
    print(
        json.dumps(
            {
                "event_count": events["count"],
                "ontology_entries": audit["ontology_entries"],
                "matched_events": audit["matched_events"],
                "unmatched_events": audit["unmatched_events"],
                "ambiguous_events": audit["ambiguous_events"],
                "new_series": EXPECTED_SERIES,
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        validate()
    else:
        materialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
