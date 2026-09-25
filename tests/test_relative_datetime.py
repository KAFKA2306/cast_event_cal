from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.relative_datetime import (
    build_resolution_audit,
    materialize_recurring_events,
    resolve_event_datetime,
    resolve_recurring_event,
)

JST = ZoneInfo("Asia/Tokyo")


def no_explicit_date(_text: str, _anchor: datetime) -> None:
    return None


def resolve(text: str, anchor: datetime):
    return resolve_event_datetime(
        text,
        anchor,
        explicit_parser=no_explicit_date,
    )


def test_friday_next_week_monday_is_three_days_later() -> None:
    anchor = datetime(2026, 8, 7, 12, 0, tzinfo=JST)
    result = resolve("来週月曜 22:00 VRChatイベント", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 10, 22, 0, tzinfo=JST)
    assert result.method == "next_calendar_week_weekday"


def test_sunday_next_week_saturday_is_six_days_later() -> None:
    anchor = datetime(2026, 8, 9, 12, 0, tzinfo=JST)
    result = resolve("来週土曜日 21:00 開催", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 15, 21, 0, tzinfo=JST)


def test_monday_next_week_friday_is_eleven_days_later() -> None:
    anchor = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve("来週の金曜日 20:30 OPEN", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 14, 20, 30, tzinfo=JST)


def test_past_current_week_weekday_is_rejected_not_rolled_forward() -> None:
    anchor = datetime(2026, 8, 4, 12, 0, tzinfo=JST)
    assert resolve("今週月曜 22:00 のイベント", anchor) is None


def test_unprefixed_weekday_uses_next_occurrence() -> None:
    anchor = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve("水曜 21:00 JOIN", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 5, 21, 0, tzinfo=JST)
    assert result.method == "next_occurrence_unprefixed"


def test_next_same_weekday_means_seven_days_later() -> None:
    anchor = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve("次の月曜 19:00 開催", anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 8, 10, 19, 0, tzinfo=JST)
    assert result.method == "next_occurrence_explicit"


def test_jst_week_boundary_is_used_even_when_anchor_is_utc() -> None:
    anchor_utc = datetime.fromisoformat("2026-08-09T14:59:00+00:00")
    result = resolve("来週月曜 00:30 開催", anchor_utc)
    assert result is not None
    assert result.anchor == datetime(2026, 8, 9, 23, 59, tzinfo=JST)
    assert result.event_at == datetime(2026, 8, 10, 0, 30, tzinfo=JST)


def test_same_day_unprefixed_future_stays_today_and_old_time_moves_next_week() -> None:
    anchor = datetime(2026, 8, 3, 18, 0, tzinfo=JST)
    future = resolve("月曜 21:00 開催", anchor)
    old = resolve("月曜 12:00 開催", anchor)
    assert future is not None and future.event_at.date() == anchor.date()
    assert old is not None and old.event_at.date().isoformat() == "2026-08-10"


def test_recovers_long_gap_relative_day_from_source_timestamp() -> None:
    anchor = datetime(2026, 9, 19, 10, 0, tzinfo=JST)
    text = (
        "本日はVRChatイベントを開催します！ "
        "Group + インスタンスで皆さまをお待ちしております。 "
        "詳しい参加方法は案内をご確認ください。 開場は21:00です。"
    )
    result = resolve(text, anchor)
    assert result is not None
    assert result.event_at == datetime(2026, 9, 19, 21, 0, tzinfo=JST)
    assert result.method == "relative_day_evidence_span"


def test_recovers_konya_fullwidth_clock() -> None:
    anchor = datetime(2026, 9, 19, 10, 0, tzinfo=JST)
    result = resolve(
        "VRChatの交流会を開催します。今夜 ２２時３０分からGroup +でOPENします。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 19, 22, 30, tzinfo=JST)


def test_recovers_spaced_calendar_date() -> None:
    anchor = datetime(2026, 8, 20, 12, 0, tzinfo=JST)
    result = resolve(
        "VRCイベント開催のお知らせ 日時: 8 / 30 (日) 0:00 Group +からjoinできます。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 8, 30, 0, 0, tzinfo=JST)
    assert result.method == "explicit_calendar_date_evidence_span"


def test_recovers_fraction_slash_calendar_date() -> None:
    anchor = datetime(2026, 8, 19, 12, 0, tzinfo=JST)
    result = resolve(
        "VRC交流イベントを開催します。08⁄20（木）21時30分からGroup +で参加できます。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 8, 20, 21, 30, tzinfo=JST)


def test_recovers_labeled_ddmmyyyy_date() -> None:
    anchor = datetime(2026, 8, 10, 12, 0, tzinfo=JST)
    result = resolve(
        "VRCHAT GROUP＋ DJイベント dd/mm/yyyy:24/08/2026(mon.) START:22:00 開催",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 8, 24, 22, 0, tzinfo=JST)
    assert result.method == "explicit_ddmmyyyy_evidence_span"


def test_recovers_konoato_as_same_day_evidence() -> None:
    anchor = datetime(2026, 9, 10, 18, 0, tzinfo=JST)
    result = resolve(
        "この後21:45からVRCイベントを開催します。Group +でご参加ください。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 10, 21, 45, tzinfo=JST)


def test_rejects_real_world_event_without_vr_access_evidence() -> None:
    anchor = datetime(2026, 9, 10, 12, 0, tzinfo=JST)
    assert resolve(
        "今夜20:00から大阪でVRChatユーザー向けDJイベントを開催します。",
        anchor,
    ) is None


def test_rejects_news_update_clock_as_event_clock() -> None:
    anchor = datetime(2026, 9, 10, 7, 0, tzinfo=JST)
    assert resolve(
        "毎朝8時更新 今日のVRChatイベントNEWS。展示イベントが開催決定しました。",
        anchor,
    ) is None


def test_rejects_visit_time_for_already_running_event() -> None:
    anchor = datetime(2026, 9, 10, 18, 0, tzinfo=JST)
    assert resolve(
        "この後21時から、現在VRCで開催 中の展示会に行くよ！",
        anchor,
    ) is None


def test_relative_tomorrow_is_not_double_applied_by_partial_date_match() -> None:
    anchor = datetime(2026, 9, 20, 23, 54, tzinfo=JST)
    result = resolve(
        "明日からVRChat花火大会を開催します。21.22日の2日間、19時開始。Group +で参加できます。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 21, 19, 0, tzinfo=JST)
    assert result.method == "relative_day_evidence_span"


def test_accepts_stream_when_vrchat_venue_is_explicit() -> None:
    anchor = datetime(2026, 8, 20, 12, 0, tzinfo=JST)
    result = resolve(
        "今夜は特別ライブ。22:30 VRChatライブ会場 OPEN！23:20 配信枠はこちら。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 8, 20, 22, 30, tzinfo=JST)


def test_rejects_ordinal_recurring_weekday_without_occurrence_date() -> None:
    anchor = datetime(2026, 9, 14, 12, 0, tzinfo=JST)
    assert resolve(
        "毎月第2、第4 日曜日 13:00~22:00開催。VRChat Groupで参加できます。",
        anchor,
    ) is None


def test_rejects_unprefixed_weekday_clock_from_past_report_context() -> None:
    anchor = datetime(2026, 9, 15, 12, 0, tzinfo=JST)
    assert resolve(
        "今日は火曜日。昨日はVRCのBAR営業でしたが、今回は20時から別ゲームを配信します。",
        anchor,
    ) is None


def test_rejects_relative_day_when_multiple_distinct_event_clocks_are_listed() -> None:
    anchor = datetime(2026, 8, 29, 9, 0, tzinfo=JST)
    assert resolve(
        "今日は盛りだくさん。19時からは別企画、20時半からVRC、22時からは別イベント。",
        anchor,
    ) is None


def test_resolution_audit_records_changed_existing_events() -> None:
    previous = [
        {
            "source_id": "yahoo:x:1",
            "starts_at": "2026-08-17T13:00:00Z",
        }
    ]
    current = [
        {
            "source_id": "yahoo:x:1",
            "starts_at": "2026-08-10T13:00:00Z",
            "date_resolution_method": "next_calendar_week_weekday",
            "date_resolution_anchor": "2026-08-07T03:00:00Z",
            "date_resolution_evidence": {"method": "next_calendar_week_weekday"},
        }
    ]
    audit = build_resolution_audit(
        previous,
        current,
        generated_at="2026-08-03T00:00:00Z",
    )
    assert audit["changed_event_count"] == 1
    assert audit["events_with_resolution_evidence"] == 1
    assert audit["changed_events"][0]["previous_starts_at"] == "2026-08-17T13:00:00Z"
    assert audit["changed_events"][0]["current_starts_at"] == "2026-08-10T13:00:00Z"


def test_materializes_weekly_recurrence_after_current_time() -> None:
    source_anchor = datetime(2026, 7, 20, 12, 0, tzinfo=JST)
    current = datetime(2026, 8, 3, 9, 0, tzinfo=JST)
    result = resolve_recurring_event(
        "毎週金曜日 22:00 VRChat交流イベント開催。Group +でJOINできます。",
        source_anchor,
        materialize_after=current,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 8, 7, 22, 0, tzinfo=JST)
    assert result.method == "recurrence_weekly_materialized"
    assert result.recurrence_rule == {
        "frequency": "weekly",
        "weekday": 4,
        "hour": 22,
        "minute": 0,
        "timezone": "Asia/Tokyo",
    }


def test_materializes_ordinal_monthly_recurrence_without_guessing() -> None:
    source_anchor = datetime(2026, 7, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 9, 14, 12, 0, tzinfo=JST)
    result = resolve_recurring_event(
        "毎月第2、第4 日曜日 13:00開催。VRChat Group +で参加できます。",
        source_anchor,
        materialize_after=current,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 27, 13, 0, tzinfo=JST)
    assert result.method == "recurrence_ordinal_monthly_materialized"
    assert result.recurrence_rule is not None
    assert result.recurrence_rule["ordinals"] == [2, 4]


def test_recurrence_materializer_rejects_commerce_clock_without_access() -> None:
    source_anchor = datetime(2026, 7, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 9, 14, 12, 0, tzinfo=JST)
    assert resolve_recurring_event(
        "毎週金曜日22:00 VRChat向け衣装セールを開催します。BOOTHで販売。",
        source_anchor,
        materialize_after=current,
    ) is None


def test_access_evidence_can_anchor_relative_datetime_without_announcement_word() -> None:
    anchor = datetime(2026, 9, 19, 10, 0, tzinfo=JST)
    result = resolve(
        "VRChat交流会 今夜22:00 Group +でJOINできます。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 19, 22, 0, tzinfo=JST)


def test_parser_can_resolve_access_clock_before_semantic_classifier_gate() -> None:
    anchor = datetime(2026, 9, 19, 10, 0, tzinfo=JST)
    result = resolve(
        "今夜22:00にVRChatへJOINして遊びます。",
        anchor,
    )
    assert result is not None

def test_materializes_multiple_weekdays_and_selects_next_occurrence() -> None:
    source_anchor = datetime(2026, 8, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 8, 3, 23, 0, tzinfo=JST)
    result = resolve_recurring_event(
        "毎週 月曜・水曜 22:00 VRChat交流会を開催。Group +でJOINできます。",
        source_anchor,
        materialize_after=current,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 8, 5, 22, 0, tzinfo=JST)
    assert result.recurrence_rule is not None
    assert result.recurrence_rule["weekdays"] == [0, 2]


def test_materializes_multiple_month_days() -> None:
    source_anchor = datetime(2026, 9, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 9, 14, 12, 0, tzinfo=JST)
    result = resolve_recurring_event(
        "毎月 1日・15日 21:30 VRChat集会を開催。Group +で参加できます。",
        source_anchor,
        materialize_after=current,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 15, 21, 30, tzinfo=JST)
    assert result.recurrence_rule is not None
    assert result.recurrence_rule["days"] == [1, 15]


def test_materializes_last_weekday_of_month() -> None:
    source_anchor = datetime(2026, 9, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 9, 14, 12, 0, tzinfo=JST)
    result = resolve_recurring_event(
        "毎月最終金曜日 22:00 VRChatイベント開催。Group +でJOINできます。",
        source_anchor,
        materialize_after=current,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 25, 22, 0, tzinfo=JST)
    assert result.recurrence_rule is not None
    assert result.recurrence_rule["frequency"] == "monthly_last_weekday"


def test_recurrence_half_hour_is_not_truncated_to_top_of_hour() -> None:
    source_anchor = datetime(2026, 9, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 9, 14, 12, 0, tzinfo=JST)
    result = resolve_recurring_event(
        "毎週金曜日 22時半 VRChat交流会を開催。Group +でJOINできます。",
        source_anchor,
        materialize_after=current,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 18, 22, 30, tzinfo=JST)


def test_period_clock_is_resolved_as_24_hour_time() -> None:
    anchor = datetime(2026, 9, 19, 10, 0, tzinfo=JST)
    result = resolve(
        "本日 VRChat交流会を開催します。Group +でJOIN、開始は午後10時半です。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 19, 22, 30, tzinfo=JST)


def test_materializes_four_bounded_future_occurrences() -> None:
    source_anchor = datetime(2026, 8, 1, 12, 0, tzinfo=JST)
    current = datetime(2026, 8, 3, 12, 0, tzinfo=JST)

    results = materialize_recurring_events(
        "毎週金曜日 22:00 VRChat交流会を開催。Group +でJOINできます。",
        source_anchor,
        materialize_after=current,
    )

    assert [item.event_at for item in results] == [
        datetime(2026, 8, 7, 22, 0, tzinfo=JST),
        datetime(2026, 8, 14, 22, 0, tzinfo=JST),
        datetime(2026, 8, 21, 22, 0, tzinfo=JST),
        datetime(2026, 8, 28, 22, 0, tzinfo=JST),
    ]

def test_recovers_midnight_japanese_and_am_clock_without_shifting_to_afternoon() -> None:
    anchor = datetime(2026, 6, 8, 7, 55, tzinfo=JST)
    result = resolve(
        "本日 深夜 #ガジェット愛好会 による WWDC 26 応援 上映会 を行います。"
        "深夜2時の VRChat でお待ちしております。6/9 (火) AM 2:00～ Group Public",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 6, 9, 2, 0, tzinfo=JST)


def test_screening_notice_keeps_existing_explicit_broadcast_datetime() -> None:
    anchor = datetime(2026, 9, 7, 12, 0, tzinfo=JST)
    result = resolve(
        "VRChat撮影作品。本編は9月13日（日）午前10時から配信開始！"
        "9月8日（火）には先行上映会も開催します。",
        anchor,
    )
    assert result is not None
    assert result.event_at == datetime(2026, 9, 13, 10, 0, tzinfo=JST)
