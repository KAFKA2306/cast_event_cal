# cast_event_cal

VRChatイベントを収集・検証し、出典付きのカレンダーを公開する正本リポジトリ。

- [公開カレンダー](https://kafka2306.github.io/cast_event_cal/)
- [今夜のイベント](https://kafka2306.github.io/cast_event_cal/tonight/)
- JSON: https://kafka2306.github.io/cast_event_cal/events.json
- iCalendar: https://kafka2306.github.io/cast_event_cal/calendar.ics

## データ処理

`data/` の投稿・公式イベント・定期開催情報を正規化し、決定論的な分類、出典IDによる重複排除、開催回単位の重複排除、ontology照合を経て `public/` にJSON・ICS・Webページ・監査結果を生成します。

- 日付・参加方法・VRChatとの関連性を推測して採用しない。相対日時は投稿時刻基準。
- 不確実な日時、権限未確認の収集、曖昧なontology照合はfail-closed。棄却理由と観測記録は保持する。
- Yahoo取得は [取得権限](docs/yahoo-collection-authorization.md) に従う。現行の許可判定は期限付きの運用者申告に基づき、権利者の許諾を独立に確認したものではない。
- イベントIDと開催回の区別は [アーキテクチャ](docs/architecture.md)、正本と配信先の境界は [公開フロー](docs/canonical-flow.md) を参照。

主要な入力: `data/recurring_events.json`、`data/one_off_events.json`、`data/discovered_events.json`、`data/x_events.json`、`data/yahoo_realtime_candidates.json`、`config/event_ontology.json`。

公開物: `public/events.json`、`public/calendar.ics`、`public/health.json`、`public/snapshot.json`。採否・日時解決・重複照合は関連する監査JSONへ記録します。

`KAFKA2306/vrc_cast_event_calender` は配信先であり、収集・分類・正本DBを持ちません。

## 開発・検証

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check cast_event_cal scripts tests
pytest -q
python scripts/materialize_events.py
python main_executor.py run --strict
python scripts/render_frontend.py
python -m http.server 8000 --directory public
```

CIはPR時にPython 3.12で実行します。公開データの更新は `.github/workflows/update-calendar-v2.yml` が毎時17分（UTC）、手動、対象コード変更時に実行します。収集成功と公開反映は分けて検証します。

利用する秘密情報は実行経路に応じて `X_BEARER_TOKEN`、`VRCHAT_AUTH_COOKIE` など。秘密値はコミットしません。Yahoo検索は許可状態の検証なしに取得しません。

ライセンス: MIT。
