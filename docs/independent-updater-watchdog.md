# GitHub定時実行の欠落に備える独立監視（#406）

2026-11-10 現在、GitHub schedule と GitHub内部のwatcherは同じ実行基盤に依存します。
- GitHub: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- Cloudflare: https://developers.cloudflare.com/workers/configuration/cron-triggers/

## 実装と安全契約

既存の Cloudflare Workers `cast-event-cal` に、サイトの静的配信を維持しつつ `53 * * * *` UTC の Cron Trigger と `scheduled` ハンドラーを追加しています。GitHub Actionsの実行基盤とは別の時刻源です。閲覧リクエストは `env.ASSETS.fetch` に渡します。

毎tickで両方を取得:
1. GitHubの `Update calendar data` のmainブランチ実行履歴（最新100件）
2. 公開URL `https://kafka2306.github.io/cast_event_cal/snapshot.json` の生成日時・件数

**両方180分以内なら正常**。どちらかが超過した場合のみ復旧を検討します。時間不明、未来時刻、API失敗、snapshot不正、最終成功が不明、1日分の履歴が100件を超えて不完全な場合は `unknown` として復旧しません。既存のrunが動作中ならdispatchしません。最近90分以内に同workflowの実行要求があればdispatchせず、直近24時間の手動dispatchが2件以上でもdispatchしません。

復旧はREST APIの `workflow_dispatch` で `recovery_attempt=1` を渡すだけです。GitHub側に既存の `concurrency` と追加の復旧制限が残ります。Cloudflare側も1本のCron Triggerにし、並列増殖を防ぎます。

## 運用開始条件（外部権限が必要）

Cloudflare Workers Buildsから本リポジトリmainのWorkerが正常デプロイされていることを先に確認してください。現存ビルド接続が自動デプロイしていればCronの追加は配置されます。ただし、**実際の独立Cron tickの実行と復旧成功は、Cloudflareの稼働ログで必ず確認**します。

復旧dispatchにはCloudflare Workerの **Secret** `GITHUB_WATCHDOG_TOKEN` が必要です。設定が無い場合は監視のみで、再起動要求を送信しません。GitHub fine-grained tokenは `KAFKA2306/cast_event_cal` の **Actions: read/write** のみに限定し、リポジトリのContents: writeを与えません。トークン値はリポジトリ・Issue・CIログに記載しません。

設定方法:
1. Cloudflare Dashboard > Workers & Pages > `cast-event-cal` > Settings > Variables and Secrets > Add Secret
2. 名前 `GITHUB_WATCHDOG_TOKEN`、値は上記権限のGitHubトークンをCloudflare上で設定
3. Cloudflare Cron Trigger が UTC 毎時53分にあること、`observability.enabled` によりログが記録されることを確認
4. Cloudflareログで `component=independent-updater-watchdog` を確認し、2tick連続で `checked_at`、`latest_success_at`、`snapshot_at`、`run_age_minutes`、`snapshot_age_minutes`、`dispatches_last_24h` をread-back
5. 擬似時刻・API障害・残存active run・24h上限等は `node --test workers/updater-watchdog.test.mjs` で検証。必要ならテスト環境で既存の安全なworkflow_dispatchを1回だけ手動検証し、本番のデータ更新runとsnapshotを照合する

Cloudflare Workers Logsには毎tick JSONとして記録し、トークン値をログ出力しません。ログ保存期間は契約次第です。GitHub Actions内のwatcherはフォールバックとして維持します。

## 未検証

- Cloudflare Cron Triggerが本番で実際に2回連続実行されたか
- Secretの設定有無と許可
- 本番での最初の自動復旧・公開snapshot更新

これらが揃うまでは #406 を閉じず、`independent_recovery=UNVERIFIED` とします。
