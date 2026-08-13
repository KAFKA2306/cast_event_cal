# cast_event_cal

**VRChatイベントは、告知を見つけただけでは参加できる情報にならない。**

日時、参加方法、募集締切、公式リンク、投稿時点が別々の場所に書かれ、定期集会と単発イベントでも扱いが違います。古い「本日開催」の投稿を検索日に読み替えたり、商品販売の投稿をイベントとして採用したりすると、公開カレンダーそのものが誤情報になります。

cast_event_calは、公開イベント・定期集会・募集締切を、出典と判定理由を残したまま整理し、JSON、iCalendar、Web UIへ変換する正本リポジトリです。正規化、重複除去、イベントオントロジー、検索シャード、fail-closed分類を使い、推測で候補を採用せず、正本と配信repoの責務を分離します。

**公開カレンダー:** https://kafka2306.github.io/vrc_cast_event_calender/  
**JSON API:** https://kafka2306.github.io/vrc_cast_event_calender/events.json  
**iCalendar:** https://kafka2306.github.io/vrc_cast_event_calender/calendar.ics

`vrc_cast_event_calender`は静的Pages配信先としてのみ使用します。

## 正本データ

- 定期系列: `data/recurring_events.json`
- 単発イベント: `data/one_off_events.json`
- VRChat公式カレンダー: `data/discovered_events.json`
- X API採用結果: `data/x_events.json`
- Yahoo当日観測スナップショット: `data/yahoo_realtime_candidates.json`
- Yahoo採用結果: `data/yahoo_realtime_events.json`
- Yahoo棄却記録: `data/yahoo_realtime_rejected.json`
- Yahoo実行状態: `data/yahoo_realtime_health.json`
- イベントオントロジー辞書: `config/event_ontology.json`
- Yahoo検索シャード辞書: `config/yahoo_query_terms.json`

## 公開・監査データ

- 統合イベント: `public/events.json`
- カレンダー: `public/calendar.ics`
- 取得状態: `public/health.json`
- Yahoo候補台帳: `public/yahoo-candidate-history.json`
- Yahoo分類監査: `public/yahoo-classifier-audit.json`
- 公開オントロジー: `public/event-ontology.json`
- オントロジー照合監査: `public/ontology-match-audit.json`
- 公開後監査: `audit/production-status.json`

## Yahoo!リアルタイム検索

### 検索・選定ポリシー v1.8

検索式は、明示的イベント種別、採用済みイベントに頻出した構造語、開催動詞とVRChat参加導線、具体的募集種別と締切の4系統で構成します。採用済みイベントからは「イベント告知」「営業告知」「通常営業」「開催決定」「Group+」「リクイン」「JOIN制」「フレンドインスタンス」「ご来店」「遊びに来て」「ステージ」などを候補化し、固有イベント名や「本日」「応募」のような汎用語は採用しません。

リポスト3件以上は引き続き必須です。そのうえで、明示的イベント種別、または開催動詞と参加導線、または参加意思表現と参加導線を要求します。商品販売、プレゼント応募、常設ワールド紹介、過去イベントの感想は構造証拠がない限り棄却します。

曜日と時刻だけの告知は、X投稿IDから復元した投稿日時を基準に次の該当曜日へ決定論的に変換します。正例語の採用状況は`public/yahoo-positive-vocabulary.json`へ出力します。


単一の巨大クエリだけでは同じ上位40件へ偏るため、検索空間を決定論的なシャードへ分割します。

対象群:

- 開催・参加・主催・集会などの中核語
- JOIN、リクイン、Request Invite、Group Instanceなどの入場語
- カフェ、バー、クラブ、居酒屋などの店舗型イベント語
- DJ、ライブ、舞台、展示、撮影、ゲーム、謎解きなどの活動語
- 言語交流、技術、研究、同期会、初心者案内などのコミュニティ語
- キャスト、スタッフ、参加者、出展者などの募集語
- 商品販売、衣装、アバター、プレゼントなどのノイズ監査語
- 本日、明日、曜日、時刻などの相対日時語

初回構築ではシャードを順番に取得し、候補台帳が1000件へ到達した時点で停止します。日次運用では基準クエリと16シャードをローテーションし、古い候補を保持したまま新しい検索領域を継続観測します。

採用には、X投稿ID、VRChat/VRC関連性、開催または募集意図、明示日時、リポスト3件以上、未来180日以内が必要です。商品販売、配布、プレゼント応募、日時欠損、過去イベント、X APIとの重複、壊れたHTML断片は理由付きで棄却します。

### 1000件以上の候補台帳

Yahooの検索画面から投稿が消えた後でもロジック改善を反映できるよう、最大5000件・365日分を保持します。

```text
複数Yahoo検索シャード
  → X投稿IDで重複排除
  → 検索語、検索群、観測回数、最大リポスト数を保存
  → X Snowflake投稿IDから投稿日時を復元
  → 台帳全件を最新ルールで毎日再判定
  → 採用・棄却・理由分布を分類監査へ保存
  → 高リポスト棄却と商用疑義採用を監査対象として抽出
```

台帳の主なフィールド:

- `status_id`
- `text` / `author` / `url`
- `first_seen_at` / `last_seen_at`
- `source_created_at`
- `retweet_count` / `max_retweet_count`
- `observation_count`
- `query_keys` / `query_groups` / `query_terms`
- `last_decision` / `last_reason`

`本日`、`今日`、`明日`などは再処理日や初回観測日ではなく、X投稿IDから復元した`source_created_at`を基準に解釈します。投稿日時を復元できない場合だけ`first_seen_at`へフォールバックします。これにより、古い投稿がYahoo検索へ再浮上しても「本日開催」として再登録されません。

### 分類ロジック

分類器はフェイルクローズです。

- リポスト数が取得できない候補は採用しない
- 商品販売・無料配布・プレゼントだけの投稿は採用しない
- 「参加方法」がフォロー、RP、いいね、リプだけの場合はイベント参加とみなさない
- 商品抽選を通すには、具体的イベント種別またはJOIN、リクイン、Group Instance等のVRChat入場手段が必要
- 誕生日・記念インスタンスは明示的な参加方法がなければ採用しない
- 告知月と明示日付の月が矛盾する候補は採用しない
- 相対日時を投稿日時基準で展開した後、現在時刻より過去なら`past_event_now`で棄却する
- 判定変更は回帰テストと分類監査の両方で固定する

`public/yahoo-classifier-audit.json`には、採用率、棄却理由分布、高リポスト棄却、商用疑義採用、重複・日時欠損などの品質指標を保存します。

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

`.github/workflows/update-calendar-v2.yml`は毎日05:17 JST、手動実行、主要ロジック変更時に起動します。

1. 定期系列を未来120日まで展開
2. VRChat公式カレンダーを取得
3. X API候補を分類
4. Yahoo基準クエリと日次16シャードを取得
5. 1000件以上の候補台帳へ統合
6. X投稿時刻を基準に台帳全件を再分類
7. 4情報源をUTC正規化・重複排除
8. オントロジー辞書で詳細と公式リンクを補完
9. JSON、ICS、レスポンシブUIを生成
10. 台帳件数、由来情報、分類理由、既知誤採用、一意性を品質ゲートで検証
11. `pull --rebase`後に生成差分をcommit
12. Pagesへ配信し、イベントAPI、1000件台帳、分類監査をHTTP検証

日常運用ではLLM判定を使用しません。追加・棄却・再分類・辞書補完は決定論的なPython処理のみで行います。

## ローカル検証

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
ruff check cast_event_cal scripts tests main_executor.py
pytest tests
python scripts/materialize_events.py
python scripts/collect_yahoo_corpus.py --mode daily --target 1000
python scripts/refine_yahoo_corpus.py
python main_executor.py run --strict
python scripts/render_frontend.py
python -m http.server 8000 --directory public
```

初回に1000件を構築する場合:

```bash
python scripts/collect_yahoo_corpus.py \
  --mode bootstrap \
  --target 1000 \
  --max-queries 140 \
  --delay-seconds 0.75 \
  --require-target
python scripts/refine_yahoo_corpus.py
```

## 品質原則

- 日時、終了時刻、隔週基準を推測しない
- 取得失敗時に正常キャッシュを空データで上書きしない
- HTML構造不明時は候補を通さない
- リポスト数不明のYahoo候補を採用しない
- 商品販売や商品抽選をイベントとして混入させない
- 古い相対日時告知を収集日のイベントとして復活させない
- オントロジーの曖昧一致を公開しない
- 採用条件変更には回帰テストを追加する
- Python 3.11、3.12、3.13のCIを通過させる
- 公開後にHTML、JSON、候補台帳、分類監査、オントロジーを監査する

## 必要なSecrets

- `X_BEARER_TOKEN`
- `VRCHAT_AUTH_COOKIE`
- `PAGES_TOKEN`（初回設定時のみ）

Yahoo!リアルタイム検索にはSecretを使用しません。

## ライセンス

MIT