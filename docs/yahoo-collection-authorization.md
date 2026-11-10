# Yahoo!リアルタイム検索: 取得権限と個人情報の取り扱い

最終更新: 2026-11-10。対象URL: `https://search.yahoo.co.jp/realtime/search`。

## 運用と権限の区別

本プロジェクトは、既存のYahoo取得・イベント公開ワークフローを、最小限の公開設定で有効化するための **operator attestation（運用者による権限の申告）** を受け付ける。この方式は **権利者の承認を独立に検証したことを意味しない**。別途、発行者による文書確認が行われた場合のみ `permission_record_approved` と記録する。

- `config/yahoo_access.json` は個人名、メール本文、契約番号、秘密URL、署名、添付資料を保存しない。
- 公開設定には、対象URL、利用目的（`automated_collection` / `public_redistribution`）、申告に基づく運用方式、内部レビュー期限のみを含める。**取得・保存・公開に必要な範囲を超える権限を示さない**。
- `operator_review_due_at` は運用者申告の再確認期日であり、発行者のライセンス期限ではない。`valid_until=null` は「発行者の期限を把握していない」を意味する。
- 内部レビュー期日を超えると `permission_status()` は `permission_review_overdue` を返し、ネットワーク取得を停止する。既存キャッシュは消さない。
- 権限の申告だけでは、利用規約上の許可範囲が客観的に確定したとは扱わない。実際の許可範囲と差が見つかった場合は公開設定を直ちに縮小・停止する。

## 機械的取得の仕様

| 項目 | 現行の仕様 |
| --- | --- |
| 検索先 | `https://search.yahoo.co.jp/realtime/search` のみ |
| 定期更新 | `.github/workflows/update-calendar-v2.yml` の毎時17分UTC |
| 取得量 | `config/yahoo_query_terms.json` の既存クエリ予算を維持、増量しない |
| 処理 | 投稿識別子・日時手掛かり・公開本文を抽出し、日時と参加方法を判定 |
| 保存先 | `data/yahoo_realtime_*.json` / `public/yahoo-candidate-history.json` |
| 公開先 | `public/events.json`、HTML、ICS、監査JSON |
| 評価 | `public/yahoo-autonomy-scorecard.json` に新規追加・失効・理由不明の消失を記録 |

権限が不十分・期限切れ・設定不正の場合は `status=skipped`、`reason=permission_*` を記録し、既存Yahooデータを維持する。Yahoo以外の承認済みsourceは更新する。Web検索サービスの一般向けヘルプは無許諾の機械的な情報収集と再利用を禁止すると案内しているため、運用時も申告済みの許可範囲と公式条件の相違を継続して確認する。

- https://support.yahoo-net.jp/PccSearch/s/article/H000015794
- https://support.yahoo-net.jp/SccRealtime/s/article/H000007996

## 監査と検証

`scripts/yahoo_collection_permission.py` は取得前に `https`、正確なホスト・パス、必要な運用範囲、レビュー期日を確認する。許諾文書の提出や個人情報のGitHubへの保管は必要としない。

設定を変更した場合、限定的テストとexact-head CIで確認し、main反映後に本番の `data/yahoo_realtime_health.json` の `queries_succeeded` と `public/yahoo-autonomy-scorecard.json` の実変化をread-backする。ネットワーク成功と新規イベント公開成功は別の指標として評価する。
