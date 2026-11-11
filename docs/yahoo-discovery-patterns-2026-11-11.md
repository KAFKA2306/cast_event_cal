# Yahoo!リアルタイム検索の発見・分類監査（2026-11-11）

観測: 2026-11-10 11:14:58 UTC。以下は当時のsnapshotの集計であり、現在値ではない。

## 検証済み

- 現存候補5,000件: accepted 160、`missing_datetime` 4,134、`missing_event_marker` 380、`giveaway_only` 228、`product_only` 84、その他14。棄却数は真の取り逃し数ではない。
- `missing_datetime` 内訳: 日時根拠なし1,946、非イベント1,114、部分的/曖昧日時668、過去296、定期開催93、parser候補17。独立の正解照合を要する再評価母集団は668+93+17=778。
- 過去16スナップショットでは異なる投稿ID17,735、いずれかで採用されたID1,700。保持上限5,000の現存ファイルだけでは過去の発見全体を測れない。
- 196クエリの内部評価: productive 6、insufficient-evidence 185、redundant 5。独立goldは1件のみで、サイト全体のrecallは未測定。
- LLMレビューキューpending1,224、resolutions0。観測開始までの遅延（4,995件）は中央値4.98時間、90パーセンタイル102.19時間。公開遅延ではない。

一次データ: [candidate](../public/yahoo-candidate-history.json) / [classifier](../public/yahoo-classifier-audit.json) / [publishability](../public/yahoo-publishability-audit.json) / [query yield](../public/yahoo-query-yield-audit.json) / [review queue](../data/yahoo_llm_review_queue.json) / [coverage gold](../config/coverage_gold.json) / [scorecard](../public/yahoo-autonomy-scorecard.json)。

過去版の監査コミット: `1a2c5247 24bb9f65 b8443ea5 266ccb01 7f5b36f0 4494136e 0e7b7207 6ac94f14 df9520b1 2de506de a0e1d69a a32d81c4 6e8e9eae aa3a4e73 01c6293d 63754b69`。

## 実装上の優先順位

1. [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190): Yahoo結果とは独立したイベント正解集合を作り、未取得/取得後棄却/公開前消失を分けて計測する。
2. [#196](https://github.com/KAFKA2306/cast_event_cal/issues/196): 英語曜日挿入、`日(土)`、OPEN/START、24時、複数開催日、定期開催を独立証拠と回帰テストで安全に評価する。
3. [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190): 抽選・商品併記・イベント固有名詞の誤棄却を再検証し、LLMレビュー結果を機械ルールへ還元する。
4. [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190): 候補上限による退出と公開差分の不明理由を記録する。

未確認: Yahooが返さなかった全イベント、画像だけにある日時、真のrecall、消失4件の原因。検索要求を増やす前に許諾と実際の掲載改善を検証する。
