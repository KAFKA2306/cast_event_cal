# Event API v1

`public/events.json` を正準公開フィードとして、`scripts/build_public_api.py` が機械利用向けの配布物を生成します。

生成先:

- `public/api/v1/events.json` — 正準JSONのバージョン付きコピー
- `public/api/v1/events.csv` — 主要列の表形式配布
- `public/api/v1/facets.json` — category/status/source/event_mode の件数集計
- `public/api/v1/manifest.json` — 件数、生成日時、source SHA-256、各配布物のSHA-256とbyte数

## 利用例

```bash
python scripts/build_public_api.py
python scripts/audit_public_feed.py public/api/v1/events.json --report build/api-audit.json
```

Pages配信後は次のURL体系を使用します。

```text
https://kafka2306.github.io/vrc_cast_event_calender/api/v1/manifest.json
https://kafka2306.github.io/vrc_cast_event_calender/api/v1/events.json
https://kafka2306.github.io/vrc_cast_event_calender/api/v1/events.csv
https://kafka2306.github.io/vrc_cast_event_calender/api/v1/facets.json
```

クライアントは `manifest.json` の `source_sha256` またはファイル別 `sha256` を比較し、変更がない場合は再取得を省略できます。`cache.max_age_seconds` は再検証間隔の目安であり、完全な鮮度保証ではありません。

CSVは検索・表計算向けの主要列だけを収録します。`official_links`、画像来歴、分類根拠などの詳細属性が必要な場合はJSONを使用してください。

## 出典と更新

イベントごとの出典は各レコードの `source`、`source_id`、`url`、`official_links` 等に保持します。公式VRChatカレンダーを人手確認した観測は `data/source_snapshots/` に取得日付きで保存します。本文の転載ではなく、日時・ID・タイトル・公開URLなど検証に必要な事実メタデータだけを保持します。
