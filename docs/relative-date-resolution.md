# Yahoo相対日時の解決規則

Yahoo!リアルタイム検索由来の投稿は、X Snowflakeから復元した投稿日時をJSTへ変換し、その時刻を相対日時のanchorとして使用する。Snowflakeを復元できない場合のみ`first_seen_at`、それもない場合のみ実行時刻へフォールバックする。

## 暦週規則

週の開始は月曜日とする。

| 表現 | 解決規則 |
|---|---|
| `今週月曜` | anchorを含む暦週の月曜。解決時刻がanchorより過去なら棄却し、次週へ繰り越さない |
| `来週月曜` | anchorの次の暦週に属する月曜 |
| `次の月曜` | 次に到来する月曜。同じ月曜に投稿された場合は7日後 |
| `月曜` | 次に到来する月曜。同日で時刻が未来なら当日、2時間より前の過去時刻なら7日後 |
| `本日` / `今日` / `明日` | anchorの日付を基準に解決 |
| 明示年月日 | 記載された日付を使用 |

`来週`は「次回出現する曜日へさらに7日加える」という計算をしない。たとえば金曜日投稿の`来週月曜`は3日後であり、10日後ではない。

## 公開証跡

採用イベントには次を保存する。

```json
{
  "date_resolution_method": "next_calendar_week_weekday",
  "date_resolution_anchor": "2026-08-07T03:00:00Z",
  "date_resolution_evidence": {
    "method": "next_calendar_week_weekday",
    "anchor": "2026-08-07T03:00:00Z",
    "resolved_at": "2026-08-10T13:00:00Z",
    "timezone": "Asia/Tokyo",
    "week_start": "monday",
    "matched_text": "来週月曜 22:00"
  }
}
```

`public/yahoo-date-resolution-audit.json`は、前回の`data/yahoo_realtime_events.json`と再分類後のイベントを`source_id`で比較し、開始日時が変化したイベント、旧日時、新日時、解決方式、anchorを列挙する。

## Fail-closed条件

- `今週＋曜日`が既に過去
- 日付または時刻を解決できない
- 解決日時が実行時点から12時間より前
- 解決日時が実行時点から180日より後

これらは未来の日付へ推測補正せず、理由付き棄却とする。
