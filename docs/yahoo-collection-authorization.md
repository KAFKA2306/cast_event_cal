# Yahoo!リアルタイム検索: 自動取得の権限境界

最終確認: 2026-11-10. 対象: `https://search.yahoo.co.jp/realtime/search`.

Yahoo!検索公式の利用案内は、許諾のない機械的な検索情報の取得、利用、および無断二次利用を禁止しています。
- https://support.yahoo-net.jp/PccSearch/s/article/H000015794
- https://support.yahoo-net.jp/SccRealtime/s/article/H000007996

**現状: `UNVERIFIED` / 自動取得停止。** 利用許諾の有無をアクセス可否や以前の成功記録から推定しません。
本リポジトリの `config/yahoo_access.json` は `approved: false` であり、Yahoo検索HTMLへのネットワーク要求は `fetch_page` の入口で拒否します。`collect_yahoo_corpus` は古い候補・イベントを消さずに `skipped / permission_unverified` を健康記録へ出し、Yahoo以外の情報源のビルドを継続します。これは**既存の掲載情報の再配布権限を認定するものではありません**。既存データの権利レビューは別途必要です。

## 取得・保存・公開の対象

| 項目 | 現行の実装 |
| --- | --- |
| 取得先 | `search.yahoo.co.jp/realtime/search` |
| 取得頻度 | `update-calendar-v2.yml` の毎時17分 UTC（許諾停止中は0件） |
| 取り込み | X投稿の識別子・投稿時刻に関する手掛かり・投稿文・検索語など |
| 正本・履歴 | `public/yahoo-candidate-history.json`、`data/yahoo_realtime_*.json` |
| 公開成果物 | `public/events.json` / HTML / ICS / Yahooの分類・収集監査JSON |
| 使用許諾 | Yahoo公式及び各投稿権利者の権利処理が必要。現時点では未検証 |

## 将来再開の条件

(1) LINEヤフー側に対象エンドポイント・機械的な定期検索・保存・公開/二次利用の可否を正式照会する。
(2) 公開可能な証拠URL、契約対象、期間、許諾範囲を審査する（非公開契約の場合は秘密条項を公開しない）。
(3) リポジトリ管理者が `config/yahoo_access.json` に `approved: true`、`authorization_reference`、`valid_until` (timezone付き ISO-8601)、`allowed_activities` (automated_collection / public_redistribution)を入力し、PRで根拠を検証する。**単にJSONを書き換えたことは権利者の承認ではありません**。
(4) ネットワーク回数・収集量は従来予算以内を維持し、増加は#190の効率測定と#405の許諾確認を通過した場合のみ。
(5) 許諾を得られなければYahooでは人間による検索結果ページへのリンクを使い、収集自体は主催者提供の公開・利用許諾済みICS/JSON等に限定する。

閲覧用リンクの案内はスクレイピングの許可と異なります。反復アクセスやアクセス制限回避は使用しません。
