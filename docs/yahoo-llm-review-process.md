# Yahoo候補のLLMレビュー

日常の採否は決定論的classifierが担当する。証拠が不足する候補を `data/yahoo_llm_review_queue.json` に重複なく保存し、既存の `data/yahoo_llm_review_resolutions.json` に判定済みの候補は再登録しない。

常時レビュー対象: `conflicting_date_context`、`missing_participation_method`、`unknown`、`retweet_count_missing`、`retweet_count_invalid`。 `missing_datetime` / `missing_event_marker` は `retweet_count >= 3` の場合のみ。商品販売・景品抽選を含む疑わしい採用候補は `possible_false_positive` として優先する。

高優先度からレビューし、`decision`（`accept` / `reject` / `needs_more_evidence`）、確定したUTC開始時刻または `null`、出典に基づく `reason`、一般化可能な `rule_candidate`、レビュー時刻を記録する。

ルール昇格には複数の独立した根拠、決定論的classifierへの実装、回帰検証、候補再分類、採否件数監査を要する。LLM判断のみで日時や実在を推測して公開しない。
