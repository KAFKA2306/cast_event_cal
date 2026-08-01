# cast_event_cal

**公開カレンダー:** https://kafka2306.github.io/vrc_cast_event_calender/  
**JSON API:** https://kafka2306.github.io/vrc_cast_event_calender/events.json  
**iCalendar:** https://kafka2306.github.io/vrc_cast_event_calender/calendar.ics  
**公開ミラー:** https://github.com/KAFKA2306/vrc_cast_event_calender

VRChatイベントの公開情報を定期取得し、出典を保持した正規化JSON、iCalendar、検索可能なWeb画面へ自動変換するパイプラインです。このリポジトリをデータ生成の正本とし、既にGitHub Pagesが稼働している公開ミラーへ成果物を同期します。

## v2で刷新した点

- Xの画面スクレイピングとID・パスワード直書きを廃止
- VRChat公式カレンダー検索、X API v2、Group Calendar、公開ICS、公開JSON、手動JSONを同じ取得層で処理
- 公開一次情報で確認した定期イベントを120日先まで開催日単位に展開
- 公式カレンダー検索から公開イベントだけをライブ発見
- 曖昧な日時を推測で確定せず、明示的な日時だけを採用
- 出典IDを優先した重複排除と、取得元ごとの失敗隔離
- `events.json`、`calendar.ics`、`health.json`、Web UIを一度に生成
- 6時間ごとのデータ生成、生成物のcommit、公開ミラーへの同期
- 60件未満を失敗させる固定系列カバレッジゲート
- 公開URLとJSON APIのHTTP 200自己監査
- Python 3.11〜3.13でCI、設定検証、単体テスト、静的解析

## データフロー

```text
公開一次情報
  → data/recurring_events.json（定期系列）
  → data/one_off_events.json（単発開催）
  → scripts/materialize_events.pyで120日分を日付展開
  → data/manual_events.json

VRChat公式カレンダー検索
  → scripts/fetch_vrchat_calendar.py
  → data/discovered_events.json

上記2系統
  → UTC正規化・重複除外
  → public/ にJSON / ICS / health / Web UIを生成
  → vrc_cast_event_calenderへ同期
  → GitHub Pages公開とHTTP 200監査
```

## 定期イベントの管理

`data/recurring_events.json`には、曜日、開始時刻、終了時刻、タイムゾーン、根拠URLを持つ系列だけを登録します。`scripts/materialize_events.py`が実行時点から過去1日・未来120日の各開催日を生成するため、同じイベントを手作業で毎週追加する必要はありません。

対応する頻度は次のとおりです。

- `weekly`: 複数曜日を指定できる週次開催
- `monthly_nth_weekday`: 第3日曜などの月次開催

終了時刻を一次情報で確認できないイベントは、推測せず`end_time`を省略します。生成後の`source_id`は系列IDと開催日の組み合わせになり、同一系列の各回を独立した予定としてJSONとICSへ出力します。

## VRChat公式カレンダーのライブ検索

Repository Secret `VRCHAT_AUTH_COOKIE`が設定されている場合、`scripts/fetch_vrchat_calendar.py`がカレンダー検索APIを利用して新規イベントを取得します。

既定の検索語:

- 日本語
- 初心者
- 交流
- 音楽
- ゲーム
- Quest

採用ルール:

- `accessType: public`だけを採用
- Draft、削除済み、カレンダーID・タイトル・開始時刻欠損を除外
- 同一カレンダーIDを統合
- 固定系列と同一タイトル・同一開始時刻の結果を除外
- Cookie未設定時は安全にスキップ
- API障害または不正なCookieの場合は直前の発見キャッシュを保持
- 実行状態を`data/discovery_health.json`へ保存

ライブ検索結果は固定系列60件以上の品質ゲートには算入しません。API結果が減少しても、確認済みカレンダーの基盤を維持します。

## ローカル実行

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
python main_executor.py validate
python scripts/materialize_events.py
python scripts/fetch_vrchat_calendar.py
python main_executor.py run --strict
python -m http.server 8000 --directory public
```

`http://localhost:8000`で確認できます。

## 取得元の追加

定期系列は`data/recurring_events.json`、単発予定は`data/one_off_events.json`へ追加します。APIまたはフィードは`config/sources.yaml`へ追加します。

```yaml
sources:
  - name: community_calendar
    type: ics
    enabled: true
    url: https://example.com/calendar.ics

  - name: community_api
    type: json
    enabled: true
    url: https://example.com/events.json
    items_path: events
```

JSONレコードでは最低限`title`と`starts_at`が必要です。日時はISO 8601を推奨します。

## X API

Repository Secretに`X_BEARER_TOKEN`を登録し、`config/sources.yaml`の`x_recent_search`または`x_list`を`enabled: true`へ変更します。X投稿からは、年月日または月日と時刻が明示された投稿のみを決定論的にイベント化します。LLMによる日時推測は行いません。

## VRChat Group Calendar

Repository Secretに`VRCHAT_AUTH_COOKIE`を登録し、実在する`group_id`を`vrchat_group`取得元へ設定します。認証情報はリポジトリへ保存しません。

## 出力

- `data/manual_events.json`: 定期系列と単発予定を展開した入力データ
- `data/discovered_events.json`: 公式カレンダー検索で発見した公開イベント
- `data/discovery_health.json`: ライブ検索の状態、件数、失敗理由
- `public/events.json`: 正規化イベントAPI
- `public/calendar.ics`: カレンダー購読用
- `public/health.json`: 取得元ごとの成功・失敗・件数
- `public/index.html`: 検索・期間絞り込みUI

取得元が一部失敗した場合、成功した取得元のデータは公開し、`health.json`を`degraded`にします。全取得元が失敗した場合は終了コード1、`--strict`では1件でも失敗すると終了コード2です。

## 自動運用

### データ生成

`cast_event_cal/.github/workflows/update-calendar.yml`が次を実行します。

1. 6時間ごと、手動実行、主要設定変更時に起動
2. 定期系列を120日先まで展開
3. VRChat公式カレンダーから公開イベントを検索
4. 取得・正規化・公開物生成
5. HTML、JSON、ICS、health、最低件数を検証
6. 差分がある場合だけデータと`public/`を自動commit・push

### 本番公開

`vrc_cast_event_calender/.github/workflows/sync-cast-event-production.yml`が次を実行します。

1. 6時間ごとまたは手動で正本の`public/`を取得
2. JSON件数、health、ICS、HTMLを検証
3. GitHub Pagesの公開元へ同期
4. 公開ページと`events.json`がHTTP 200になるまで確認
5. `audit/production-status.json`へ公開監査結果を保存

CIは`.github/workflows/ci.yml`でPython 3.11〜3.13を検証します。

## セキュリティ

- APIトークン、Cookie、`.env`、ブラウザ認証状態をGitへ追加しない
- Xのユーザー名・パスワードを使用しない
- `accessType: public`以外をライブ検索結果へ含めない
- 招待制・非公開イベントを公開イベントと断定しない
- 開催時刻や終了時刻を推測しない
- API障害時に空データで正常なキャッシュを上書きしない
- 取得元の利用規約、API上限、削除・中止情報を優先する

## ライセンス

MIT
