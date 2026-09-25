from cast_event_cal.categories import classify_events, direct_decision, load_category_ontology
from scripts.build_yahoo_rejection_sample_audit import build as build_rejection_sample_audit


def event(title: str, description: str = "", **values):
    return {
        "id": values.pop("id", title),
        "title": title,
        "description": description,
        "category": values.pop("category", "event"),
        "organizer": values.pop("organizer", "@example"),
        "location": values.pop("location", "VRChat"),
        "tags": values.pop("tags", ["VRChat"]),
        **values,
    }


def test_actual_display_examples_get_semantic_categories():
    ontology = load_category_ontology()
    examples = [
        (event("VRChat韓国語教室 アリラン", "ハングル基礎と発音の講義を開催"), "learning"),
        (event("アイスクリーム集会", "みんなで食べて交流する集会"), "community"),
        (event("VRC世界史講義", "通史で世界史を解説する講義形式"), "learning"),
        (event("ARTLINK2026 美術展説明会", "VR美術館の作品展示と出展方法を説明"), "art"),
        (event("VRCフィットボクシング集会", "動画を見ながら運動するフィットネス集会"), "wellness"),
        (event("ワールド巡りツアー", "景観ワールドを観光します"), "world_tour"),
    ]
    for row, expected in examples:
        assert direct_decision(row, ontology).category == expected


def test_stream_is_modality_not_genre():
    ontology = load_category_ontology()
    decision = direct_decision(event("技術学術イベント配信", "VRChat会場とYouTube配信で研究発表を行います"), ontology)
    assert decision.category == "technology"
    assert decision.event_mode == "hybrid"


def test_offline_vrc_adjacent_post_is_flagged_as_offline():
    ontology = load_category_ontology()
    decision = direct_decision(event("渋谷でDJします", "VRCとは関係ないイベントです。渋谷でJPOPパーティを開催します"), ontology)
    assert decision.category == "music"
    assert decision.event_mode == "offline"


def test_generic_event_does_not_default_to_performance():
    ontology = load_category_ontology()
    decision = direct_decision(event("VRChatイベント告知", "8月10日21時から開催します"), ontology)
    assert decision.category == "other"
    assert decision.source == "fallback"


def test_curated_ontology_override_wins():
    ontology = load_category_ontology()
    decision = direct_decision(event("0属オークション", "参加条件あり", ontology_id="zerozoku-auction", ontology_category="game"), ontology)
    assert decision.category == "game"
    assert decision.source == "curated_ontology"
    assert decision.confidence == 0.99


def test_keyword_predictions_do_not_train_organizer_prior():
    ontology = load_category_ontology()
    rows = [
        event("DJイベント NIGHT ONE", "VRChatクラブでDJ party", organizer="@nightone", id="one"),
        event("クラブイベント NIGHT ONE", "DJとダンスの夜", organizer="@nightone", id="two"),
        event("今週も開催します", "22時にGroup+へJoin", organizer="@nightone", id="three"),
    ]
    classified, summary, _ = classify_events(rows, ontology)
    assert [row["category"] for row in classified] == ["music", "music", "other"]
    assert classified[2]["category_source"] == "fallback"
    assert summary["organizer_profile_count"] == 0


def test_curated_seeds_fill_weak_rows_and_preserve_seed_provenance():
    ontology = load_category_ontology()
    rows = [
        event("ONE", organizer="@trusted", id="one", ontology_id="one", ontology_category="music"),
        event("TWO", organizer="@trusted", id="two", ontology_id="two", ontology_category="music"),
        event("今週も開催します", "22時にGroup+へJoin", organizer="@trusted", id="three"),
    ]
    classified, summary, _ = classify_events(rows, ontology)
    assert classified[2]["category"] == "music"
    assert classified[2]["category_source"] == "organizer_prior"
    assert "seed_event_ids:one,two" in classified[2]["category_evidence"]
    assert summary["organizer_profiles"]["trusted"]["seed_evidence"] == [
        {"event_id": "one", "category": "music", "source": "curated_ontology"},
        {"event_id": "two", "category": "music", "source": "curated_ontology"},
    ]


def test_recruitment_deadline_keeps_explicit_category():
    ontology = load_category_ontology()
    decision = direct_decision(event("キャスト募集締切", "応募期限は8月10日", category="recruitment_deadline"), ontology)
    assert decision.category == "recruitment_deadline"
    assert decision.event_mode == "deadline"


def test_yahoo_rejection_sample_audit_covers_each_reason_and_prefers_high_retweets():
    payload = build_rejection_sample_audit([
        {"status_id": "1", "reason": "missing_datetime", "retweet_count": 2, "text_excerpt": "a"},
        {"status_id": "2", "reason": "missing_datetime", "retweet_count": 9, "text_excerpt": "b"},
        {"status_id": "3", "reason": "product_only", "retweet_count": 4, "text_excerpt": "c"},
    ])
    assert payload["materialized_rejected_count"] == 3
    assert payload["reason_count"] == 2
    reasons = {row["reason"]: row for row in payload["reasons"]}
    assert reasons["missing_datetime"]["samples"][0]["status_id"] == "2"
    assert reasons["product_only"]["samples"][0]["status_id"] == "3"


def test_source_provenance_tags_do_not_become_category_evidence():
    ontology = load_category_ontology()
    decision = direct_decision(
        event(
            "仮想学生集会",
            "学生同士がお喋りしながら交流するイベントです",
            tags=["外部カレンダー", "技術・学術"],
        ),
        ontology,
    )
    assert decision.category == "community"
    assert all("技術・学術" not in evidence for evidence in decision.evidence)


def test_observed_external_calendar_examples_follow_primary_intent():
    ontology = load_category_ontology()
    provenance_tags = ["外部カレンダー", "技術・学術"]
    examples = [
        (
            event(
                "株式投資座談会",
                "株式投資について交流し、最後に写真撮影を行います",
                tags=provenance_tags,
            ),
            "community",
        ),
        (
            event(
                "VRC MED J SALON",
                "医学論文のAIまとめを医師が議論しながら修正します",
                tags=provenance_tags,
            ),
            "technology",
        ),
        (
            event(
                "VRC微分音集会",
                "微分音・Xenharmonicの音楽理論や調律理論について交流します",
                tags=provenance_tags,
            ),
            "music",
        ),
        (
            event(
                "VR酔い訓練集会",
                "VR酔いを軽減するための訓練集会です",
                tags=provenance_tags,
            ),
            "wellness",
        ),
        (
            event(
                "Blender＆Unity技術交流会",
                "BlenderとUnityを使う制作者同士で交流します",
                tags=provenance_tags,
            ),
            "technology",
        ),
    ]
    for row, expected in examples:
        assert direct_decision(row, ontology).category == expected
