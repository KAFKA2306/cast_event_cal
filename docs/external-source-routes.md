# 外部イベント取得ルート

`cast_event_cal`は、各取得元の利用条件と障害を分離するため、外部カレンダーを`scripts/fetch_external_calendars.py`で収集し、`data/external_events.json`へ正規化してから既存パイプラインへ投入します。

## 取得元

### VRChat公式イベントカレンダー

`scripts/fetch_vrchat_calendar.py`は、VRChat公式APIの次の2経路を併用します。

1. `/calendar/discover`: upcomingイベントをカーソルで列挙する一次経路
2. `/calendar/search`: 日本語・初心者・交流・音楽・ゲーム・Questを検索する補完経路

`cal_...`と`grp_...`が揃うイベントは、VRChat公式の共有可能なイベントURLへ変換します。非公開、draft、削除済みイベントは採用しません。

### 技術・学術系イベントHub

`config/external_calendars.yaml`に、VRC技術・学術系イベントHubが公開するGoogleカレンダーの公開ICSを登録しています。RRULE、EXDATE、RECURRENCE-ID、TZIDをUTCへ正規化し、公開表示はAsia/Tokyoを維持します。

### イベント公式サイト

`config/event_ontology.json`の`official_links`から、次のkindだけを取得候補にします。

- `official_website`
- `event_home`
- `announcement`
- `official_event_page`

X、VRChat、Discord、Google Forms等は公式サイトHTML取得の対象外です。対象ページにSchema.orgの`Event`またはその派生型（`EducationEvent`等）のJSON-LDがある場合だけ、日時・主催者・会場・画像・URLを採用します。日時を本文から推測するスクレイピングは行いません。

### VRCEve

VRCEveは、事前許可のない継続的な自動取得や外部サービスへの組み込みを利用規約で制限しています。そのためHTMLスクレイピングは実装していません。

許諾済みのICSフィードを提供された場合だけ、Repository Secretsへ次を設定します。

- `VRCEVE_DATA_USE_APPROVED=true`
- `VRCEVE_ICS_URL=<許諾済みフィードURL>`

許諾フラグがない実行では`vrceve_authorized_feed`を`skipped`としてhealthへ記録し、アクセスしません。

## 重複排除

外部イベントは、次の順で既存4系統と照合します。

1. canonicalized URLの完全一致
2. NFKC正規化したタイトルと開始時刻（分単位）の完全一致

照合対象:

- `data/manual_events.json`
- `data/discovered_events.json`
- `data/x_events.json`
- `data/yahoo_realtime_events.json`

タイトルの曖昧類似だけでは統合しません。

## 障害時の扱い

取得元単位で失敗を隔離します。失敗した取得元については、前回の`data/external_events.json`に同じ`source`名で残る正常キャッシュを保持します。監査結果は`data/external_discovery_health.json`へ出力します。

主なフィールド:

- `status`: `ok` / `degraded` / `skipped`
- `event_count`
- `deduplicated_against_existing`
- `sources[].status`
- `sources[].stale_cache_count`
- `sources[].source_page`
- `sources[].policy_url`

## ローカル実行

```bash
python scripts/fetch_external_calendars.py
python main_executor.py run --strict
pytest -q tests/test_external_calendar_sources.py tests/test_vrchat_discovery_routes.py
```
