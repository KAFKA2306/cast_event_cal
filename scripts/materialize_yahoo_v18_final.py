from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_line(lines: list[str], value: str, start: int = 0) -> int:
    for index in range(start, len(lines)):
        if lines[index] == value:
            return index
    raise RuntimeError(f"line not found: {value}")


def replace_set(lines: list[str], name: str, body: list[str]) -> None:
    start = find_line(lines, f"{name} = {{")
    end = find_line(lines, "}", start + 1)
    lines[start : end + 1] = [f"{name} = {{", *[f"    {row}" for row in body], "}"]


def repair_and_run_source_migration() -> None:
    path = ROOT / "scripts/apply_yahoo_policy_v18.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "def structured_classify(text: str) -> tuple[str | None, str | None]:\n"
        "    folded = text.casefold()\n",
        "def structured_classify(text: str) -> tuple[str | None, str | None]:\n",
        1,
    )
    text = text.replace(
        '    queries = "\\n".join(row["query"] for row in plan)',
        '    queries = "\\\\n".join(row["query"] for row in plan)',
        1,
    )
    path.write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def refine_classifier() -> None:
    path = ROOT / "scripts/collect_yahoo_corpus.py"
    lines = path.read_text(encoding="utf-8").splitlines()

    private = find_line(lines, "PRIVATE_INSTANCE_TERMS = {")
    lines[private:private] = [
        "VR_ACCESS_TERMS = {",
        '    "join", "ジョイン", "リクイン", "reqin", "リクエストインバイト", "request invite",',
        '    "フレンド申請", "フレリク", "グループインスタンス", "group instance", "group+",',
        '    "グループ＋", "group public", "フレンドインスタンス", "join制",',
        '    "インスタンスへ", "インスタンスに", "インスタンスオープン",',
        "}",
        'GENERIC_EVENT_NOUN_TERMS = {"イベント", "event"}',
        "BROADCAST_ONLY_TERMS = {",
        '    "配信予定", "コラボ配信", "ライブ配信", "youtube配信", "配信枠", "生配信",',
        "}",
    ]

    specific_start = find_line(lines, "SPECIFIC_EVENT_TERMS = {")
    specific_end = find_line(lines, "}", specific_start + 1)
    lines[specific_end:specific_end] = [
        '    "vrchatライブ", "performance live", "講習会",',
    ]

    replace_set(
        lines,
        "ATTENDANCE_TERMS",
        [
            '"参加したい", "参加できます", "参加ください", "ご参加ください", "来場", "ご来場",',
            '"ご来店", "遊びに来て", "遊びにきて", "お越し", "見に来て", "聴きに来て",',
            '"お待ちしております", "お待ちしてます", "入場",',
        ],
    )

    feature = find_line(lines, "    has_specific_event = has_any(text, SPECIFIC_EVENT_TERMS)")
    lines.insert(feature + 1, "    has_generic_event = has_any(text, GENERIC_EVENT_NOUN_TERMS)")
    access = find_line(lines, "    has_access = has_any(text, PARTICIPATION_TERMS)", feature)
    lines[access] = "    has_access = has_any(text, VR_ACCESS_TERMS)"
    giveaway = find_line(
        lines,
        "    has_giveaway = has_any(text, implementation.GIVEAWAY_TERMS)",
        feature,
    )
    lines.insert(giveaway + 1, "    has_broadcast = has_any(text, BROADCAST_ONLY_TERMS)")

    structure = find_line(
        lines,
        "    event_structure = has_specific_event or (has_action and has_access) or (has_access and has_attendance)",
        feature,
    )
    lines[structure : structure + 1] = [
        "    event_structure = (",
        "        has_specific_event",
        "        or (has_generic_event and has_action)",
        "        or (has_generic_event and has_attendance)",
        "        or (has_action and has_access)",
        "        or (has_access and has_attendance)",
        "    )",
    ]
    recruitment = find_line(
        lines,
        "    recruitment_structure = has_recruitment or (has_deadline and has_access)",
        feature,
    )
    lines[recruitment + 1 : recruitment + 1] = [
        "    if has_broadcast and not has_access and not has_attendance:",
        '        return None, "missing_event_marker"',
    ]

    refined = find_line(lines, "def refined_candidate_to_event(")
    call = find_line(lines, "    event, reason = _ORIGINAL_CANDIDATE_TO_EVENT(", refined)
    lines[call:call] = [
        "    if has_any(text, PRIVATE_INSTANCE_TERMS) and not has_participation:",
        '        return None, "missing_participation_method"',
        "",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_regression_tests() -> None:
    path = ROOT / "tests/test_yahoo_selection_policy.py"
    text = path.read_text(encoding="utf-8")
    marker = "def test_streaming_schedule_without_vrchat_entry_is_rejected"
    if marker in text:
        return
    text += '''


def test_generic_vrc_event_with_attendance_language_is_accepted():
    event, reason = classify(
        "8/14 22:00 VRCイベント Dark Five Clubに出演します。是非お越しください"
    )
    assert reason is None
    assert event is not None


def test_vrchat_live_with_opening_time_is_accepted():
    event, reason = classify(
        "VRChatライブ Lumina Performance Live 8/6 22:15開場 22:30開演、Group開催"
    )
    assert reason is None
    assert event is not None


def test_training_session_with_fullwidth_group_plus_is_accepted():
    event, reason = classify(
        "VRCバドミントン部初心者講習会 8/8 22:00開催。集合場所はグループ＋"
    )
    assert reason is None
    assert event is not None


def test_streaming_schedule_without_vrchat_entry_is_rejected():
    event, reason = classify(
        "2026/8/8 22:00 VRChatコラボ配信予定。謎解きを配信します。YouTubeで見てね"
    )
    assert event is None
    assert reason == "missing_event_marker"
'''
    path.write_text(text, encoding="utf-8")


def apply() -> None:
    repair_and_run_source_migration()
    refine_classifier()
    add_regression_tests()


def validate() -> None:
    history = json.loads((ROOT / "public/yahoo-candidate-history.json").read_text(encoding="utf-8"))
    events = json.loads((ROOT / "data/yahoo_realtime_events.json").read_text(encoding="utf-8"))
    rejected = json.loads((ROOT / "data/yahoo_realtime_rejected.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "public/yahoo-classifier-audit.json").read_text(encoding="utf-8"))
    vocabulary = json.loads((ROOT / "public/yahoo-positive-vocabulary.json").read_text(encoding="utf-8"))
    accepted_ids = {row["source_id"].split(":")[-1] for row in events}
    rejected_by_id = {row["status_id"]: row["reason"] for row in rejected}
    history_by_id = {row["status_id"]: row for row in history["candidates"]}
    expected_restored = {
        "2082264781936037965",
        "2083118271105311023",
        "2083145652478136497",
        "2083153781156610203",
        "2083522584138883522",
    }

    assert history["candidate_count"] >= 1000
    assert history["schema_version"] == "2.3"
    assert audit["schema_version"] == "1.3"
    assert audit["classifier_version"] == "1.8"
    assert audit["accepted_count"] == len(events) == 32
    assert audit["accepted_count"] + audit["rejected_count"] == history["candidate_count"]
    assert expected_restored <= accepted_ids
    assert "2074822308578173164" in accepted_ids
    assert rejected_by_id.get("2083591757128954342") == "missing_event_marker"
    assert rejected_by_id.get("2083398056188518660") == "giveaway_only"
    assert rejected_by_id.get("2083153426167578665") == "giveaway_only"
    assert all(
        int(
            history_by_id[status_id].get("max_retweet_count")
            or history_by_id[status_id].get("retweet_count")
            or 0
        )
        >= 3
        for status_id in accepted_ids
    )
    assert audit["quality"]["duplicate_status_ids"] == 0
    assert audit["quality"]["missing_source_created_at"] == 0
    assert audit["quality"]["ambiguous_decisions"] == 0
    assert vocabulary["positive_event_count"] == len(events)
    assert vocabulary["minimum_retweets"] == 3
    assert {"イベント告知", "通常営業", "リクイン"} & set(vocabulary["adopted_terms"])
    assert {"本日", "応募"} <= set(vocabulary["excluded_as_too_generic"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("apply", "validate"))
    args = parser.parse_args()
    if args.command == "apply":
        apply()
    else:
        validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
