# cast_event_cal

**公開カレンダー:** https://kafka2306.github.io/vrc_cast_event_calender/  
**JSON API:** https://kafka2306.github.io/vrc_cast_event_calender/events.json  
**iCalendar:** https://kafka2306.github.io/vrc_cast_event_calender/calendar.ics

VRChatの公開イベント、定期集会、募集締切を、日時・参加方法・公式リンク・出典を保持したJSON、ICS、Web UIへ変換する正本リポジトリです。`vrc_cast_event_calender`は静的Pages配信先としてのみ使用します。

## 正本データ

- 定期系列: `data/recurring_events.json`
- 単発イベント: `data/one_off_events.json`
- VRChat公式カレンダー: `data/discovered_events.json`
- X API採用結果: `data/x_events.json`
- Yahoo!リアルタイム検索の採用結果: `data/yahoo_realtime_events.json`
- Yahoo棄却記録: `data/yahoo_realtime_rejected.json`
- Yahoo実行状態: `data/yahoo_realtime_health.json`
- イベントオントロジー辞書: `config/event_ontology.json`

## 公開・監査データ

- 統合イベント: `public/events.json`
- カレンダー: `public/calendar.ics`
- 取得状態: `public/health.json`
- Yahoo候補台帳: `public/yahoo-candidate-history.json`
- 公開オントロジー: `public/event-ontology.json`
- オントロジー照合監査: `public/ontology-match-audit.json`
- 公開後監査: `audit/production-status.json`

## Yahoo!リアルタイム検索

毎日、次の検索条件を機械取得します。

```text
(イベント OR 参加方法 OR 参加条件 OR 開催 OR 主催 OR join OR ジョイン OR リクイン OR reqin OR リクエストインバイト OR "request invite" OR 本日 OR 営業 OR 応募) (VRChat OR VRC)
```

採用には、X投稿ID、VRChat/VRC関連性、開催または募集意図、明示日時、リポスト3件以上、未来180日以内が必要です。商品販売、配布、抽選、日時欠損、過去イベント、X APIとの重複、壊れたHTML断片は理由付きで棄却します。

### 30日候補台帳

Yahooの検索画面から投稿が消えた後でもロジック改善を反映できるよう、すべての候補を30日間保存します。

```text
Yahoo検索結果
  → 投稿候補を台帳へ追記
  → first_seen_at / last_seen_at / 最大リポスト数を保存
  → 台帳全件を最新ルールで毎日再判定
  → 過去の誤棄却候補を自動昇格
  → 採用・棄却・昇格件数をhealthへ記録
```

`本日`、`今日`、`明日`は再処理日ではなく`first_seen_at`を基準に解釈します。Yahooへの接続に失敗しても、保存済み台帳の再評価は継続できます。

## イベントオントロジー

`config/event_ontology.json`はイベントごとの機械可読辞書です。

登録可能な情報:

- `canonical_id` / 正式名称 / 別名
- 正式主催者
- 必須識別パターン
- 公式サイト、VRChat Group、公式X、告知ページ
- 参加方法
- 開催形式
- 対象者
- 既定会場とタグ

照合はフェイルクローズです。

- あいまい検索を使わない
- 必須パターンだけでは一致させない
- 別名一致、または「正式主催者一致かつ必須パターン全一致」が必要
- 同点候補は補完せず`ambiguous`として監査へ隔離
- 辞書にない情報を推測しない

一致イベントには`ontology_id`、`official_links`、`participation_method`、`event_format`、`audience`を追加します。公開ページでは公式告知と主催者公式リンクを別ボタンで表示します。

## 自動運用

`.github/workflows/update-calendar.yml`は毎日05:17 JST、手動実行、主要ロジック変更時に起動します。

1. 定期系列を未来120日まで展開
2. VRChat公式カレンダーを取得
3. X API候補を分類
4. Yahoo候補を取得し30日台帳へ統合
5. 台帳全件を最新ルールで再判定
6. 4情報源をUTC正規化・重複排除
7. オントロジー辞書で詳細と公式リンクを補完
8. JSON、ICS、レスポンシブUIを生成
9. 候補台帳、棄却理由、辞書照合、件数、一意性を品質ゲートで検証
10. `pull --rebase`後に生成差分をcommit
11. Pagesへ配信しHTTP、件数、オントロジー公開を監査

日常運用ではLLM判定を使用しません。追加・棄却・再昇格・辞書補完は決定論的なPython処理のみで行います。

## ローカル検証

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
ruff check cast_event_cal scripts tests main_executor.py
pytest tests
python scripts/materialize_events.py
python scripts/run_yahoo_realtime.py
python main_executor.py run --strict
python scripts/render_frontend.py
python -m http.server 8000 --directory public
```

Yahoo接続なしで保存済み候補だけを再評価する場合:

```bash
python scripts/replay_yahoo_history.py
```

## 品質原則

- 日時、終了時刻、隔週基準を推測しない
- 取得失敗時に正常キャッシュを空データで上書きしない
- HTML構造不明時は候補を通さない
- リポスト数不明のYahoo候補を採用しない
- 商品販売や抽選をイベントとして混入させない
- オントロジーの曖昧一致を公開しない
- 採用条件変更には回帰テストを追加する
- Python 3.11、3.12、3.13のCIを通過させる
- 公開後にHTML、JSON、オントロジー、最低件数を監査する

## 必要なSecrets

- `X_BEARER_TOKEN`
- `VRCHAT_AUTH_COOKIE`
- `PAGES_TOKEN`（初回設定時のみ）

Yahoo!リアルタイム検索にはSecretを使用しません。

## ライセンス

MIT
