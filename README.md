# cast_event_cal

**公開カレンダー:** https://kafka2306.github.io/cast_event_cal/  
**JSON API:** https://kafka2306.github.io/cast_event_cal/events.json  
**iCalendar:** https://kafka2306.github.io/cast_event_cal/calendar.ics

VRChatの公開イベント、定期集会、募集締切を、出典と時刻を保持したJSON・ICS・Web UIへ変換してGitHub Pagesで公開するリポジトリです。データ生成、公開、公開後監査を`cast_event_cal`だけで完結させます。

## 現在の構成

- 確認済み定期系列: `data/recurring_events.json`
- 単発イベント: `data/one_off_events.json`
- VRChat公式カレンダー発見結果: `data/discovered_events.json`
- X検索の採用結果: `data/x_events.json`
- 統合後の公開API: `public/events.json`
- カレンダー購読: `public/calendar.ics`
- 取得状態: `public/health.json`
- 公開後監査: `audit/production-status.json`

## データフロー

```text
確認済みグループ情報
  → data/recurring_events.json
  → scripts/materialize_events.py
  → data/manual_events.json

VRChat公式カレンダー
  → scripts/fetch_vrchat_calendar.py
  → data/discovered_events.json

X API v2 Recent Search
  → scripts/fetch_x_events.py
  → 日時解析・カテゴリ分類・ノイズ除外・public_metrics判定
  → data/x_events.json

上記3系統
  → main_executor.pyでUTC正規化・重複除外
  → public/events.json / calendar.ics / health.json
  → scripts/render_frontend.pyでWeb UI生成
  → GitHub Pagesへ直接デプロイ
  → HTTP 200・件数・UI構造を監査
```

## 定期イベント

`data/recurring_events.json`には、開催日と開始時刻を明示情報から確定できる系列だけを登録します。

対応する周期:

- `weekly`: 毎週または複数曜日
- `weekly` + `interval_weeks` + `anchor_date`: 基準日が確認できる隔週・数週おき
- `monthly_nth_weekday`: 第1・第3木曜など
- `monthly_days`: 毎月10日・20日・30日など

「不定期」「頃」「隔週だが基準週不明」「休止中」は推測して展開しません。終了時刻が確認できない場合は`end_time`を省略します。

## Xイベント発見

`scripts/fetch_x_events.py`は次の検索を既定値として使用します。

```text
lang:ja (イベント OR 参加方法 OR 参加条件 OR 開催 OR 主催 OR join OR ジョイン OR リクイン OR reqin OR リクエストインバイト OR "request invite" OR 本日 OR 営業 OR 応募) (VRChat OR VRC) -is:retweet -is:reply
```

X API v2のRecent Searchは直近7日を対象にします。画面検索で使われる`min_retweets:3`はAPI v2の検索演算子として使わず、`tweet.fields=public_metrics`で取得した`retweet_count`をコード側で判定します。

採用ルール:

- 年月日または月日と時刻が本文に明示された投稿だけを採用
- 日本語の月日時刻はJSTとしてUTCへ変換
- リポスト3件以上、または「参加方法」「開催」「営業」「締切」など強い開催マーカーがある投稿を採用
- イベントと募集締切を別カテゴリに分類
- BOOTH販売、発売、プレゼント企画だけの投稿は除外
- API障害・Secret未設定時は直前キャッシュを保持

## UI

`web/index.template.html`を正本とし、`scripts/render_frontend.py`が`public/index.html`を生成します。

- 日付別アジェンダ表示
- イベント名・主催・タグの全文検索
- 7日・30日・120日の期間切替
- カテゴリ・情報源フィルター
- イベントと募集締切の分離
- 今日、7日以内、有効情報源の集計
- JSON APIとICS購読への導線
- モバイルで横スクロールしないレスポンシブ構成

## ローカル実行

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
python main_executor.py validate
python scripts/materialize_events.py
python scripts/fetch_vrchat_calendar.py
python scripts/fetch_x_events.py
python main_executor.py run --strict
python scripts/render_frontend.py
python -m http.server 8000 --directory public
```

## 自動運用

`.github/workflows/update-calendar.yml`は6時間ごと、手動実行、主要ファイル変更時に起動します。

1. 定期系列を未来120日まで展開
2. VRChat公式カレンダーを取得
3. X API検索結果を分類
4. 3系統を正規化・重複排除
5. Web UIを生成
6. 25系列以上、250開催以上、3情報源を品質ゲートで検証
7. 生成差分をcommit
8. GitHub Pagesへ直接デプロイ
9. 公開ページ、JSON API、UI構造を監査
10. `audit/production-status.json`へ結果を記録

必要なRepository Secret:

- `X_BEARER_TOKEN`
- `VRCHAT_AUTH_COOKIE`
- `PAGES_TOKEN`（Pages初回有効化時のみ）

## セキュリティと品質

- APIトークン、Cookie、`.env`をGitへ追加しない
- `accessType: public`以外のVRChatイベントを公開しない
- 開催時刻・終了時刻・隔週基準日を推測しない
- 取得失敗時に正常なキャッシュを空データで上書きしない
- 商品販売やプレゼント企画を参加イベントとして混入させない
- 取得元ごとの件数と状態を`health.json`に残す
- 公開後にHTMLとJSONのHTTP 200、最低件数、UI識別子を検証する

## ライセンス

MIT
