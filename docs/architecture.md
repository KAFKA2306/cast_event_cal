# 正本アーキテクチャ

`cast_event_cal` は収集、分類、出典ID、開催回重複排除、ontology、`public/` を所有する。`KAFKA2306/vrc_cast_event_calender` は配信のみ。

処理順: source観測 → 正規化・同一source record排除（`cast_event_cal/core.py`）→ 出典とリンクの補強 → 開催回単位の重複排除（`scripts/deduplicate_occurrences.py`）→ ontology付与 → JSON/ICS/Web公開。

- `source_record_id`: 出典ごとの投稿・イベントID
- `occurrence_id`: 利用者が参加する開催回のID
- `provenance[]`: 統合元の全出典

開催回の自動統合には開始時刻と同一公式URL、十分に固有なタイトル、同一主催者と一致する告知内容などの強い証拠が必要。タイトル類似だけでは統合しない。開催日・回数・主催者が異なる場合は原則別開催回。

公開時の不変条件: `1 occurrence = 1 public/events.json row = 1 calendar.ics VEVENT`。ID一意性、ICS UID数、統合前後件数の整合を `public/event-duplicate-audit.json` と公開ワークフローで検証する。曖昧な統合候補は推測処理せず監査へ記録する。

`public/` は正本から生成した投影であり、入力データの代わりにはしない。
