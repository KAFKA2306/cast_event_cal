from cast_event_cal.categories import classify_events, direct_decision, load_category_ontology


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
    decision = direct_decision(
        event("技術学術イベント配信", "VRChat会場とYouTube配信で研究発表を行います"),
        ontology,
    )
    assert decision.category == "technology"
    assert decision.event_mode == "hybrid"


def test_offline_vrc_adjacent_post_is_flagged_as_offline():
    ontology = load_category_ontology()
    decision = direct_decision(
        event("渋谷でDJします", "VRCとは関係ないイベントです。渋谷でJPOPパーティを開催します"),
        ontology,
    )
    assert decision.category == "music"
    assert decision.event_mode == "offline"


def test_generic_event_does_not_default_to_performance():
    ontology = load_category_ontology()
    decision = direct_decision(event("VRChatイベント告知", "8月10日21時から開催します"), ontology)
    assert decision.category == "other"
    assert decision.source == "fallback"


def test_curated_ontology_override_wins():
    ontology = load_category_ontology()
    decision = direct_decision(
        event(
            "0属オークション",
            "参加条件あり",
            ontology_id="zerozoku-auction",
            ontology_category="game",
        ),
        ontology,
    )
    assert decision.category == "game"
    assert decision.source == "curated_ontology"
    assert decision.confidence == 0.99


def test_repeated_organizer_profile_only_fills_weak_rows():
    ontology = load_category_ontology()
    rows = [
        event("DJイベント NIGHT ONE", "VRChatクラブでDJ party", organizer="@nightone", id="one"),
        event("クラブイベント NIGHT ONE", "DJとダンスの夜", organizer="@nightone", id="two"),
        event("今週も開催します", "22時にGroup+へJoin", organizer="@nightone", id="three"),
    ]
    classified, summary, audit = classify_events(rows, ontology)
    assert [row["category"] for row in classified] == ["music", "music", "music"]
    assert classified[2]["category_source"] == "organizer_prior"
    assert summary["organizer_profile_count"] == 1
    assert not [row for row in audit if row["event_id"] == "three"]


def test_recruitment_deadline_keeps_explicit_category():
    ontology = load_category_ontology()
    decision = direct_decision(
        event("キャスト募集締切", "応募期限は8月10日", category="recruitment_deadline"),
        ontology,
    )
    assert decision.category == "recruitment_deadline"
    assert decision.event_mode == "deadline"
