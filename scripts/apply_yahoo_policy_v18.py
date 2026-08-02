from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, pattern: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, got {count}: {pattern[:100]}")
    target.write_text(updated, encoding="utf-8")


def update_config() -> None:
    path = ROOT / "config/yahoo_query_terms.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.update(
        {
            "schema_version": "1.2",
            "classifier_version": "1.8",
            "daily_query_count": 18,
            "base_queries": [
                "(イベント OR 集会 OR 交流会 OR 営業 OR 公演 OR ライブ OR DJ OR 大会 OR 朗読会 OR 朗読劇 OR 朗読ミュージカル OR 舞台 OR 上映会 OR 映画祭 OR 展示会 OR 撮影会 OR フェス OR 祭り OR オフ会 OR 説明会 OR 体験会) (VRChat OR VRC)",
                "(イベント告知 OR 営業告知 OR 通常営業 OR 開催決定 OR OPEN OR オープン) (JOIN OR ジョイン OR リクイン OR reqin OR Group+ OR グループインスタンス OR フレンドインスタンス OR 参加方法) (VRChat OR VRC)",
                "(JOIN OR ジョイン OR リクイン OR reqin OR リクエストインバイト OR \"request invite\" OR Group+ OR グループインスタンス OR フレンド申請) (開催 OR 告知 OR 日時 OR OPEN OR オープン OR 開場 OR 開始 OR 営業 OR 本日 OR 今日 OR 明日 OR 今夜) (VRChat OR VRC)",
                "(キャスト募集 OR スタッフ募集 OR 店員募集 OR 演者募集 OR テスター募集 OR 参加者募集 OR 出展募集 OR 公募) (締切 OR 〆切 OR 応募期限 OR 面接) (VRChat OR VRC)",
            ],
            "positive_feedback": {
                "source": "accepted_yahoo_events",
                "minimum_retweets": 3,
                "adoption_policy": "reusable_structural_terms_only",
                "terms": [
                    "イベント告知",
                    "営業告知",
                    "通常営業",
                    "開催決定",
                    "開催します",
                    "OPEN",
                    "Group+ instance",
                    "Group+インスタンス",
                    "リクイン",
                    "JOIN制",
                    "フレンドインスタンス",
                    "参加方法",
                    "ご来店お待ち",
                    "遊びに来て",
                    "お待ちしております",
                    "ステージ",
                ],
                "excluded_as_too_generic": ["本日", "主催", "応募", "写真", "案内"],
            },
            "term_groups": {
                "core": [
                    "イベント告知",
                    "営業告知",
                    "通常営業",
                    "開催決定",
                    "集会",
                    "交流会",
                    "公演",
                    "ライブイベント",
                    "開場",
                    "オープン",
                    "説明会",
                    "体験会",
                    "試写会",
                    "オフ会",
                    "祭り",
                    "フェス",
                ],
                "access": [
                    "JOIN制",
                    "Group+ instance",
                    "Group+インスタンス",
                    "ジョイン",
                    "リクイン",
                    "reqin",
                    "リクエストインバイト",
                    "request invite",
                    "Group Instance",
                    "グループインスタンス",
                    "フレンドインスタンス",
                    "フレンド申請",
                    "フレリク",
                    "インスタンスオープン",
                    "Group Public",
                ],
                "venues": [
                    "カフェ営業",
                    "Cafe OPEN",
                    "バー営業",
                    "Bar OPEN",
                    "クラブ営業",
                    "Club OPEN",
                    "居酒屋営業",
                    "スナック営業",
                    "キャバクラ営業",
                    "ホストイベント",
                    "喫茶営業",
                    "交流イベント",
                    "初心者案内イベント",
                ],
                "activities": [
                    "DJイベント",
                    "VJイベント",
                    "ダンスイベント",
                    "演奏会",
                    "音楽会",
                    "歌ステージ",
                    "ライブイベント",
                    "朗読会",
                    "朗読劇",
                    "朗読ミュージカル",
                    "映画祭",
                    "上映会",
                    "舞台公演",
                    "展示会",
                    "展覧会",
                    "撮影会",
                    "フォトコン",
                    "ワールド巡り",
                    "ワールドツアー",
                    "謎解きイベント",
                    "ゲーム大会",
                    "人狼会",
                    "麻雀大会",
                    "将棋大会",
                    "ボードゲーム会",
                    "TRPG会",
                    "クイズ大会",
                    "オークションイベント",
                    "競技大会",
                ],
                "communities": [
                    "言語交流会",
                    "英会話集会",
                    "日本語交流会",
                    "学術集会",
                    "技術勉強会",
                    "研究交流会",
                    "勉強会",
                    "講演会",
                    "セミナー",
                    "教育イベント",
                    "学校説明会",
                    "同期会",
                    "地域交流会",
                    "改変交流会",
                    "アバター交流会",
                    "クリエイター交流会",
                    "開発者交流会",
                    "VRC初心者案内",
                ],
                "recruitment": [
                    "キャスト募集",
                    "スタッフ募集",
                    "店員募集",
                    "演者募集",
                    "テスター募集",
                    "参加者募集",
                    "出展募集",
                    "公募",
                    "応募期限",
                    "面接",
                ],
                "commerce_noise": [
                    "BOOTH",
                    "販売",
                    "発売",
                    "配布",
                    "セール",
                    "商品",
                    "衣装",
                    "アバター",
                    "プレゼント",
                    "キャンペーン",
                    "giveaway",
                    "Patreon",
                    "無料配布",
                    "フォロー＆RP",
                ],
                "temporal_audit": [
                    "本日",
                    "今日",
                    "明日",
                    "今夜",
                    "今週",
                    "週末",
                    "月曜日",
                    "火曜日",
                    "水曜日",
                    "木曜日",
                    "金曜日",
                    "土曜日",
                    "日曜日",
                    "21時",
                    "22時",
                    "23時",
                    "0時",
                ],
            },
        }
    )
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_collector() -> None:
    constants = '''PARTICIPATION_TERMS = {
    "参加方法", "参加条件", "join", "ジョイン", "リクイン", "reqin", "リクエストインバイト",
    "request invite", "招待", "フレンド申請", "フレリク", "グループインスタンス",
    "group instance", "group+", "group public", "フレンドインスタンス", "join制",
    "インスタンスへ", "インスタンスに", "インスタンスオープン",
}
PRIVATE_INSTANCE_TERMS = {
    "誕生日インスタンス", "birthday instance", "記念インスタンス", "インスタンスを開催",
}
SPECIFIC_EVENT_TERMS = {
    "イベント告知", "営業告知", "通常営業", "開催決定", "ホストイベント", "交流イベント",
    "集会", "交流会", "オークション", "ライブイベント", "公演", "djイベント", "vjイベント",
    "歌ステージ", "ステージ", "ワールドツアー", "ワールド巡り", "謎解き", "大会", "勉強会",
    "講演会", "講演", "セミナー", "上映会", "映画祭", "朗読会", "朗読劇",
    "朗読ミュージカル", "舞台公演", "演奏会", "音楽会", "撮影会", "展示会", "展覧会",
    "フェス", "festival", "祭り", "オフ会", "説明会", "体験会", "試写会", "フォトコン",
}
EVENT_ACTION_TERMS = {"開催", "open", "オープン", "開場", "開始", "営業", "公演", "実施", "開演"}
ATTENDANCE_TERMS = {
    "参加", "ご参加", "来場", "ご来場", "ご来店", "遊びに来て", "お越し", "見に来て",
    "聴きに来て", "お待ちしております", "お待ちしてます", "入場",
}
SPECIFIC_RECRUITMENT_TERMS = {
    "キャスト募集", "スタッフ募集", "店員募集", "演者募集", "テスター募集", "参加者募集",
    "出展募集", "公募", "応募期限", "面接",
}
DEADLINE_TERMS = {"締切", "〆切", "応募期限", "までに", "応募完了"}
SOCIAL_ENTRY_TERMS = {"フォロー", "リポスト", "rp", "rt", "いいね", "リプ", "コメント", "抽選応募"}
WORLD_DESCRIPTION_TERMS = {"ワールド紹介", "ワールドを更新", "常設", "いつでも", "販売開始", "公開しました"}
GENERIC_EVENT_TERMS = {"開催", "イベント", "キャンペーン", "募集", "応募"}
AUDIT_GROUPS = {"commerce_noise", "temporal_audit"}
QUERY_CONTEXT = "(開催 OR 告知 OR 日時 OR OPEN OR オープン OR 開場 OR 開始 OR 営業 OR 本日 OR 今日 OR 明日 OR 今夜 OR 参加 OR JOIN OR リクイン OR Group+)"
'''
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        r"PARTICIPATION_TERMS = \{.*?GENERIC_EVENT_TERMS = \{.*?\}\n",
        constants,
    )

    helpers = '''def parse_event_datetime_v18(text: str, anchor: datetime) -> datetime | None:
    parsed = _ORIGINAL_PARSE_EVENT_DATETIME(text, anchor)
    if parsed is not None:
        return parsed
    normalized = implementation.normalize_text(text)
    clock = r"(?P<hour>[01]?\\d|2[0-3])(?:[:時](?P<minute>\\d{2})?)"
    match = re.search(
        rf"(?P<prefix>次(?:の)?|来週(?:の)?|今週(?:の)?)?\\s*(?P<weekday>[月火水木金土日])曜日?"
        rf".{{0,100}}?{clock}",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    target = {name: index for index, name in enumerate("月火水木金土日")}[match.group("weekday")]
    days_ahead = (target - anchor.weekday()) % 7
    prefix = match.group("prefix") or ""
    if prefix.startswith("来週"):
        days_ahead += 7
    elif prefix.startswith("次") and days_ahead == 0:
        days_ahead = 7
    day = (anchor + timedelta(days=days_ahead)).date()
    result = datetime(
        day.year,
        day.month,
        day.day,
        int(match.group("hour")),
        int(match.group("minute") or 0),
        tzinfo=JST,
    )
    if not prefix and days_ahead == 0 and result < anchor - timedelta(hours=2):
        result += timedelta(days=7)
    return result


def structured_classify(text: str) -> tuple[str | None, str | None]:
    folded = text.casefold()
    if not implementation.VRCHAT_RE.search(text):
        return None, "not_vrchat"
    has_specific_event = has_any(text, SPECIFIC_EVENT_TERMS)
    has_action = has_any(text, EVENT_ACTION_TERMS)
    has_access = has_any(text, PARTICIPATION_TERMS)
    has_attendance = has_any(text, ATTENDANCE_TERMS)
    has_recruitment = has_any(text, SPECIFIC_RECRUITMENT_TERMS)
    has_deadline = has_any(text, DEADLINE_TERMS)
    has_product = has_any(text, implementation.PRODUCT_TERMS)
    has_giveaway = has_any(text, implementation.GIVEAWAY_TERMS)
    has_social_entry = has_any(text, SOCIAL_ENTRY_TERMS)
    looks_like_world_description = has_any(text, WORLD_DESCRIPTION_TERMS)
    event_structure = has_specific_event or (has_action and has_access) or (has_access and has_attendance)
    recruitment_structure = has_recruitment or (has_deadline and has_access)
    if has_giveaway and has_social_entry and not event_structure:
        return None, "giveaway_only"
    if has_giveaway and not event_structure:
        return None, "giveaway_only"
    if has_product and not event_structure and not recruitment_structure:
        return None, "product_only"
    if looks_like_world_description and not has_specific_event and not (has_action and has_access):
        return None, "missing_event_marker"
    if recruitment_structure:
        return "recruitment_deadline", None
    if event_structure:
        return "event", None
    return None, "missing_event_marker"


def query_for_group(group: str, term: str) -> str:
    if group == "recruitment":
        return f"({term}) (締切 OR 〆切 OR 応募期限 OR 面接 OR 募集) (VRChat OR VRC)"
    if group == "access":
        return f"({term}) {QUERY_CONTEXT} (VRChat OR VRC)"
    if group in AUDIT_GROUPS:
        return f"({term}) (VRChat OR VRC)"
    return f"({term}) {QUERY_CONTEXT} (VRChat OR VRC)"


'''
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        r"def refined_candidate_to_event\(",
        helpers + "def refined_candidate_to_event(",
    )

    replace_once(
        "scripts/collect_yahoo_corpus.py",
        r"_ORIGINAL_CANDIDATE_TO_EVENT = implementation\.candidate_to_event\n",
        "_ORIGINAL_CANDIDATE_TO_EVENT = implementation.candidate_to_event\n_ORIGINAL_PARSE_EVENT_DATETIME = implementation.parse_event_datetime\n",
    )
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        r"def configure_classifier\(\) -> None:\n    ledger\.configure\(\)\n    implementation\.PARSER_VERSION = \"1\.5\"\n    implementation\.candidate_to_event = refined_candidate_to_event",
        "def configure_classifier() -> None:\n    ledger.configure()\n    implementation.PARSER_VERSION = \"1.8\"\n    implementation.classify = structured_classify\n    implementation.parse_event_datetime = parse_event_datetime_v18\n    implementation.EVENT_TERMS = SPECIFIC_EVENT_TERMS | EVENT_ACTION_TERMS | PARTICIPATION_TERMS\n    implementation.candidate_to_event = refined_candidate_to_event",
    )
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        r"query = f\"\(\{term\}\) \(VRChat OR VRC\)\"",
        "query = query_for_group(str(group), term)",
    )
    replace_once(
        "scripts/collect_yahoo_corpus.py",
        r"def select_daily_plan\(plan: list\[dict\[str, str\]\], now: datetime, count: int\) -> list\[dict\[str, str\]\]:\n    base = \[row for row in plan if row\[\"group\"\] == \"base\"\]\n    shards = \[row for row in plan if row\[\"group\"\] != \"base\"\]\n    count = max\(1, min\(count, len\(shards\)\)\)\n    offset = \(now\.astimezone\(JST\)\.date\(\)\.toordinal\(\) \* count\) % len\(shards\)\n    return base \+ \(shards\[offset:\] \+ shards\[:offset\]\)\[:count\]",
        '''def select_daily_plan(plan: list[dict[str, str]], now: datetime, count: int) -> list[dict[str, str]]:
    base = [row for row in plan if row["group"] == "base"]
    production = [row for row in plan if row["group"] not in AUDIT_GROUPS | {"base"}]
    audit = [row for row in plan if row["group"] in AUDIT_GROUPS]
    production_count = max(1, min(max(count - 2, 1), len(production)))
    audit_count = min(2, len(audit))
    ordinal = now.astimezone(JST).date().toordinal()
    production_offset = (ordinal * production_count) % len(production)
    selected = base + (production[production_offset:] + production[:production_offset])[:production_count]
    if audit_count:
        audit_offset = (ordinal * audit_count) % len(audit)
        selected += (audit[audit_offset:] + audit[:audit_offset])[:audit_count]
    return selected''',
    )


def update_refiner() -> None:
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        r"AUDIT_PATH = Path\(\"public/yahoo-classifier-audit\.json\"\)",
        'AUDIT_PATH = Path("public/yahoo-classifier-audit.json")\nPOSITIVE_VOCABULARY_PATH = Path("public/yahoo-positive-vocabulary.json")',
    )
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        r"implementation\.PARSER_VERSION = \"1\.7\"",
        'implementation.PARSER_VERSION = "1.8"',
    )
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        r'"schema_version": "1\.2"',
        '"schema_version": "1.3"',
    )
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        r'"schema_version": "2\.2"',
        '"schema_version": "2.3"',
    )
    vocabulary_function = '''def build_positive_vocabulary(events: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    config = corpus.read_json(corpus.CONFIG_PATH, {})
    feedback = config.get("positive_feedback", {}) if isinstance(config, dict) else {}
    terms = feedback.get("terms", []) if isinstance(feedback, dict) else []
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for raw_term in terms:
        term = str(raw_term).strip()
        if not term:
            continue
        matching = [
            str(event.get("source_id"))
            for event in events
            if term.casefold() in str(event.get("description") or "").casefold()
        ]
        counts[term] = len(matching)
        examples[term] = matching[:5]
    adopted = [term for term, count in counts.items() if count > 0]
    return {
        "schema_version": "1.0",
        "generated_at": implementation.utc_text(now),
        "source": "accepted_yahoo_events",
        "positive_event_count": len(events),
        "minimum_retweets": 3,
        "adoption_policy": "reusable_structural_terms_only",
        "adopted_terms": adopted,
        "term_counts": counts,
        "example_event_ids": examples,
        "excluded_as_too_generic": feedback.get("excluded_as_too_generic", []),
    }


'''
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        r"def main\(\) -> int:",
        vocabulary_function + "def main() -> int:",
    )
    replace_once(
        "scripts/refine_yahoo_corpus.py",
        r"implementation\.write_json\(implementation\.OUTPUT_PATH, accepted\)\n",
        "implementation.write_json(implementation.OUTPUT_PATH, accepted)\n    implementation.write_json(POSITIVE_VOCABULARY_PATH, build_positive_vocabulary(accepted, now))\n",
    )


def update_workflow_and_docs() -> None:
    workflow = ROOT / ".github/workflows/update-calendar-v2.yml"
    text = workflow.read_text(encoding="utf-8")
    text = text.replace("parser_version') == '1.7'", "parser_version') == '1.8'")
    text = text.replace("history.get('schema_version') == '2.2'", "history.get('schema_version') == '2.3'")
    text = text.replace("classifier_audit.get('schema_version') == '1.2'", "classifier_audit.get('schema_version') == '1.3'")
    text = text.replace("classifier_audit.get('classifier_version') == '1.7'", "classifier_audit.get('classifier_version') == '1.8'")
    workflow.write_text(text, encoding="utf-8")

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8").replace("分類器v1.7", "分類器v1.8")
    marker = "## Yahoo!リアルタイム検索\n"
    section = '''## Yahoo!リアルタイム検索

### 検索・選定ポリシー v1.8

検索式は、明示的イベント種別、採用済みイベントに頻出した構造語、開催動詞とVRChat参加導線、具体的募集種別と締切の4系統で構成します。採用済みイベントからは「イベント告知」「営業告知」「通常営業」「開催決定」「Group+」「リクイン」「JOIN制」「フレンドインスタンス」「ご来店」「遊びに来て」「ステージ」などを候補化し、固有イベント名や「本日」「応募」のような汎用語は採用しません。

リポスト3件以上は引き続き必須です。そのうえで、明示的イベント種別、または開催動詞と参加導線、または参加意思表現と参加導線を要求します。商品販売、プレゼント応募、常設ワールド紹介、過去イベントの感想は構造証拠がない限り棄却します。

曜日と時刻だけの告知は、X投稿IDから復元した投稿日時を基準に次の該当曜日へ決定論的に変換します。正例語の採用状況は`public/yahoo-positive-vocabulary.json`へ出力します。

'''
    if marker in text and "### 検索・選定ポリシー v1.8" not in text:
        text = text.replace(marker, section, 1)
    readme.write_text(text, encoding="utf-8")


def add_tests() -> None:
    path = ROOT / "tests/test_yahoo_selection_policy.py"
    path.write_text(
        '''from datetime import UTC, datetime

from scripts.collect_yahoo_corpus import (
    build_query_plan,
    configure_classifier,
    read_json,
    refined_candidate_to_event,
)


def candidate(text: str, *, retweets: int = 10) -> dict[str, object]:
    return {
        "status_id": "2084000000000000000",
        "url": "https://x.com/host/status/2084000000000000000",
        "text": text,
        "author": "host",
        "retweet_count": retweets,
    }


def classify(text: str, *, retweets: int = 10, now: datetime | None = None):
    configure_classifier()
    return refined_candidate_to_event(
        candidate(text, retweets=retweets),
        now=now or datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
        min_retweets=3,
        x_ids=set(),
    )


def test_positive_feedback_terms_are_used_in_query_plan():
    config = read_json(__import__("pathlib").Path("config/yahoo_query_terms.json"), {})
    plan = build_query_plan(config)
    queries = "\n".join(row["query"] for row in plan)
    assert "イベント告知" in queries
    assert "通常営業" in queries
    assert "Group+ instance" in queries
    assert "朗読ミュージカル" in queries
    assert "(本日) (VRChat OR VRC)" in queries


def test_explicit_performance_type_is_accepted():
    event, reason = classify(
        "8月19日22:30 VRChatで朗読ミュージカルを上演します。ご来場をお待ちしております"
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-19T13:30:00Z"


def test_weekday_time_and_group_access_are_accepted():
    event, reason = classify(
        "日曜日のTo MeはVRC公式Groupに加入して20:50になったら第1インスタンスへJOIN。遊びに来てください",
        now=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
    )
    assert reason is None
    assert event is not None
    assert event["starts_at"] == "2026-08-02T11:50:00Z"


def test_world_description_without_event_structure_is_rejected():
    event, reason = classify(
        "VRChatの映画ポスター常設ワールドを更新しました。いつでも遊びに来てください。8/19 22:00"
    )
    assert event is None
    assert reason == "missing_event_marker"


def test_product_giveaway_with_participation_word_is_rejected():
    event, reason = classify(
        "8/4 23:59 VRChat向け衣装を抽選でプレゼント。参加方法はフォローとRP"
    )
    assert event is None
    assert reason == "giveaway_only"


def test_retweet_threshold_remains_hard_gate():
    event, reason = classify(
        "8/19 22:30 VRChat朗読会を開催。Group+インスタンスへJOIN",
        retweets=2,
    )
    assert event is None
    assert reason == "retweet_below_threshold"


def test_specific_recruitment_deadline_is_kept():
    event, reason = classify(
        "VRChat店舗のキャスト募集。応募期限8/19 22:30、面接はGroupインスタンスで実施"
    )
    assert reason is None
    assert event is not None
    assert event["category"] == "recruitment_deadline"
''',
        encoding="utf-8",
    )
    corpus_test = ROOT / "tests/test_yahoo_corpus.py"
    text = corpus_test.read_text(encoding="utf-8").replace('"temporal",', '"temporal_audit",')
    corpus_test.write_text(text, encoding="utf-8")


def main() -> int:
    update_config()
    update_collector()
    update_refiner()
    update_workflow_and_docs()
    add_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
