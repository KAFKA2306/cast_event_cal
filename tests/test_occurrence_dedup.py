from scripts.deduplicate_occurrences import deduplicate_events


def event(
    *,
    event_id: str,
    source_id: str,
    title: str,
    description: str,
    starts_at: str = "2026-08-15T13:00:00Z",
    organizer: str = "@host",
    url: str | None = None,
) -> dict:
    return {
        "id": event_id,
        "source": "yahoo_realtime_events",
        "source_id": source_id,
        "title": title,
        "description": description,
        "starts_at": starts_at,
        "organizer": organizer,
        "location": "VRChat",
        "url": url or f"https://x.com/{organizer.lstrip('@')}/status/{source_id}",
        "status": "scheduled",
        "tags": ["VRChat", "Yahoo!リアルタイム検索"],
        "confidence": 0.9,
        "fetched_at": "2026-08-15T10:01:32Z",
    }


def test_same_text_same_start_cross_organizer_collapses_to_one_occurrence():
    description = (
        "【！VRChat イベント告知！】 「なんと、18ちゃんの誕生日！」 "
        "18ちゃん2周年記念イベント開催！ 1周年記念から会場が進化しました！ "
        "ぜひ18ちゃんユーザー達で集まってお話しましょう！ PC、Quest両対応なので"
        "気軽に来てください！ 日時: 8/15(土) 22:00〜 場所: グループインスタンス END"
    )
    rows = [
        event(
            event_id="1cf39843d8850c5d5159",
            source_id="yahoo:x:2088231134018867622",
            organizer="@18_khsnhonbu",
            title="18ちゃん2周年記念イベント開催！",
            description=description,
        ),
        event(
            event_id="37fb72a1a34e952bd00a",
            source_id="yahoo:x:2088293741744263229",
            organizer="@Livia14481176",
            title="18ちゃん2周年記念イベント開催！",
            description=description,
        ),
    ]

    deduped, audit = deduplicate_events(rows)

    assert len(deduped) == 1
    assert deduped[0]["id"] == deduped[0]["occurrence_id"]
    assert deduped[0]["merged_source_count"] == 2
    assert len(deduped[0]["provenance"]) == 2
    assert audit["duplicate_occurrence_count"] == 1
    assert audit["clusters"][0]["reasons"] == ["exact_text_same_start"]


def test_same_organizer_same_start_same_ordinal_collapses_updated_announcement():
    first = event(
        event_id="1f7566d3f86a1a581901",
        source_id="yahoo:x:2087828658388111441",
        organizer="@0zoku_vrc",
        title="START VRCイベント 〜０属オークション〜 第4回開催 RT招待キャンペーン",
        description=(
            "START VRCイベント 〜０属オークション〜 第4回開催 RT招待キャンペーン！ "
            "開催日時 8/15(土) 22:00 リクイン抽選式 参加条件は5万UC以上。 "
            "参加方法: リクイン抽選式。参加条件と観戦条件は各回の公式告知を確認。 "
            "開催形式: VRChat内オークションイベント 対象: 所定のUC所持条件を満たす参加者・観戦者"
        ),
    )
    second = event(
        event_id="4ba1973663bfa8149dbe",
        source_id="yahoo:x:2088561328206262511",
        organizer="@0zoku_vrc",
        title="START VRCオークションイベント 『０属オークション』 本日22:00 第4回開催",
        description=(
            "START VRCオークションイベント 『０属オークション』 本日22:00 第4回開催 "
            "出品サキュバス公開 参加方法 時間になったらインスタンスリーダーに1回リクイン。 "
            "参加方法: リクイン抽選式。参加条件と観戦条件は各回の公式告知を確認。 "
            "開催形式: VRChat内オークションイベント 対象: 所定のUC所持条件を満たす参加者・観戦者"
        ),
    )

    deduped, audit = deduplicate_events([first, second])

    assert len(deduped) == 1
    assert deduped[0]["merged_source_count"] == 2
    assert audit["duplicate_occurrence_count"] == 1
    assert "same_organizer_same_start_ordinal" in audit["clusters"][0]["reasons"]


def test_same_series_different_date_is_not_merged():
    rows = [
        event(
            event_id="auction-4",
            source_id="post-4",
            title="０属オークション 第4回開催",
            description="０属オークション 第4回開催 8/15 22:00 参加方法はリクイン",
        ),
        event(
            event_id="auction-5",
            source_id="post-5",
            title="０属オークション 第5回開催",
            description="０属オークション 第5回開催 8/22 22:00 参加方法はリクイン",
            starts_at="2026-08-22T13:00:00Z",
        ),
    ]

    deduped, audit = deduplicate_events(rows)

    assert len(deduped) == 2
    assert audit["duplicate_occurrence_count"] == 0


def test_same_start_similar_title_different_organizer_is_not_merged():
    rows = [
        event(
            event_id="beginner-a",
            source_id="post-a",
            organizer="@alpha",
            title="VRChat初心者交流会",
            description="VRChat初心者交流会です。初参加者向けに操作説明と交流を行います。",
        ),
        event(
            event_id="beginner-b",
            source_id="post-b",
            organizer="@beta",
            title="VRChat初心者交流会",
            description="VRChat初心者交流会です。写真撮影とワールド巡りを中心に交流します。",
        ),
    ]

    deduped, audit = deduplicate_events(rows)

    assert len(deduped) == 2
    assert audit["duplicate_occurrence_count"] == 0


def test_same_organizer_same_start_different_ordinal_is_not_merged():
    rows = [
        event(
            event_id="round-4",
            source_id="round-post-4",
            title="イベント 第4回",
            description="VRChatイベント 第4回開催 参加方法はGroup Joinです。",
        ),
        event(
            event_id="round-5",
            source_id="round-post-5",
            title="イベント 第5回",
            description="VRChatイベント 第5回開催 参加方法はGroup Joinです。",
        ),
    ]

    deduped, audit = deduplicate_events(rows)

    assert len(deduped) == 2
    assert audit["duplicate_occurrence_count"] == 0
    assert audit["unresolved_ambiguous_cluster_count"] >= 1


def test_dedup_is_idempotent_for_already_merged_occurrence():
    original = [
        event(
            event_id="one",
            source_id="post-one",
            title="同一イベント告知",
            description="VRChatで同一イベントを8/15 22:00から開催します。参加方法はGroup Joinです。",
            organizer="@first",
        ),
        event(
            event_id="two",
            source_id="post-two",
            title="同一イベント告知",
            description="VRChatで同一イベントを8/15 22:00から開催します。参加方法はGroup Joinです。",
            organizer="@second",
        ),
    ]

    first, first_audit = deduplicate_events(original)
    second, second_audit = deduplicate_events(first)

    assert len(first) == len(second) == 1
    assert first[0]["occurrence_id"] == second[0]["occurrence_id"]
    assert second[0]["merged_source_count"] == 2
    assert first_audit["duplicate_occurrence_count"] == 1
    assert second_audit["duplicate_occurrence_count"] == 0
