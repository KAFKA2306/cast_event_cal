# cast_event_cal

**公開カレンダー:** https://kafka2306.github.io/vrc_cast_event_calender/  
**JSON API:** https://kafka2306.github.io/vrc_cast_event_calender/events.json  
**iCalendar:** https://kafka2306.github.io/vrc_cast_event_calender/calendar.ics  
**公開ミラー:** https://github.com/KAFKA2306/vrc_cast_event_calender

VRChatイベントの公開情報を定期取得し、出典を保持した正規化JSON、iCalendar、検索可能なWeb画面へ自動変換するパイプラインです。このリポジトリをデータ生成の正本とし、既にGitHub Pagesが稼働している公開ミラーへ成果物を同期します。

## v2で刷新した点

- Xの画面スクレイピングとID・パスワード直書きを廃止
- X API v2、VRChat Group Calendar、公開ICS、公開JSON、手動JSONを同じ取得層で処理
- 曖昧な日時を推測で確定せず、明示的な日時だけを採用
- 出典IDを優先した重複排除と、取得元ごとの失敗隔離
- `events.json`、`calendar.ics`、`health.json`、Web UIを一度に生成
- 6時間ごとのデータ生成、生成物のcommit、公開ミラーへの同期
- 公開URLとJSON APIのHTTP 200自己監査
- Python 3.11〜3.13でCI、設定検証、単体テスト、静的解析

## データフロー

```text
公開JSON / ICS / X API / VRChat Group Calendar / 手動JSON
  → 取得元ごとに収集・失敗隔離
  → UTCへ正規化（表示はAsia/Tokyo）
  → 出典IDまたは主催者・タイトル・日時・会場で同一性判定
  → 公開期間でフィルタ
  → public/ にJSON / ICS / health / Web UIを生成
  → vrc_cast_event_calenderへ同期
  → GitHub Pages公開とHTTP 200監査
```

## ローカル実行

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
python main_executor.py validate
python main_executor.py run
python -m http.server 8000 --directory public
```

`http://localhost:8000`で確認できます。

## 取得元の追加

`config/sources.yaml`を編集します。

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

- `public/events.json`: 正規化イベントAPI
- `public/calendar.ics`: カレンダー購読用
- `public/health.json`: 取得元ごとの成功・失敗・件数
- `public/index.html`: 検索・期間絞り込みUI

取得元が一部失敗した場合、成功した取得元のデータは公開し、`health.json`を`degraded`にします。全取得元が失敗した場合は終了コード1、`--strict`では1件でも失敗すると終了コード2です。

## 自動運用

### データ生成

`cast_event_cal/.github/workflows/update-calendar.yml`が次を実行します。

1. 6時間ごと、手動実行、主要設定変更時に起動
2. 取得・正規化・公開物生成
3. HTML、JSON、ICS、healthの整合性検証
4. 差分がある場合だけ`public/`を自動commit・push

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
- 公開情報のみを対象とし、招待制・非公開イベントを公開イベントと断定しない
- 取得元の利用規約、API上限、削除・中止情報を優先する

## ライセンス

MIT
