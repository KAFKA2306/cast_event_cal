# Yahoo LLM review process

## Purpose

Yahoo!リアルタイム検索の候補は、まず GitHub Actions の決定論的ルールで毎日処理する。
機械判定の根拠が不足する候補だけを `data/yahoo_llm_review_queue.json` に蓄積し、LLM作業時にまとめて判定する。

## Daily machine path

1. Yahoo候補を収集する。
2. 決定論的classifierで accept / reject を判定する。
3. 正規化・アーカイブポリシーを適用する。
4. 機械判定が難しい候補と疑わしいacceptだけをレビューキューへ送る。
5. `status_id` で重複排除する。
6. `data/yahoo_llm_review_resolutions.json` に存在する判定済み候補は再度キューへ入れない。

## Queue policy

常にLLMレビューへ送る理由:

- `conflicting_date_context`
- `missing_participation_method`
- `unknown`
- `retweet_count_missing`
- `retweet_count_invalid`

条件付きで送る理由:

- `missing_datetime`
- `missing_event_marker`

上記2理由は `retweet_count >= 3` の候補だけをレビュー対象とする。

機械的にacceptされた候補でも、commerce/giveaway系の語を含み誤検知リスクがあるものは `possible_false_positive` として high priority でレビューする。

## LLM batch review

LLM作業時は `priority=high` から処理し、1バッチごとに同一基準でまとめて判定する。
各候補について次を出す。

- `decision`: `accept` / `reject` / `needs_more_evidence`
- `normalized_starts_at`: ISO-8601 UTC。確定できなければ `null`
- `reason`: 投稿本文・日時・参加方法など、確認できた証拠に基づく短い理由
- `rule_candidate`: 同種候補を次回から機械処理できる決定論的ルール案。一般化できなければ `null`

判定結果は `data/yahoo_llm_review_resolutions.json` の `resolutions` に追記する。

推奨レコード:

```json
{
  "status_id": "...",
  "decision": "accept",
  "normalized_starts_at": "2026-08-10T13:00:00Z",
  "reason": "投稿本文に開催日・開始時刻・Group+参加方法が明記されている",
  "rule_candidate": "『Group+』と明示日時が同時にある場合は参加方法ありとして扱う",
  "reviewed_at": "2026-08-09T00:00:00Z",
  "reviewer": "llm"
}
```

## Rule promotion

LLM判定を単発修正で終わらせない。
同じ `rule_candidate` が複数件で成立し、既存accept/rejectを壊さないテストが書ける場合だけclassifierへ昇格する。

昇格時は必ず:

1. classifierへ決定論的ルールを追加する。
2. 回帰テストを追加する。
3. 全候補を再分類する。
4. accepted / rejected / queue件数の変化を監査する。
5. 次回以降、そのパターンをLLMキューへ送らない。

## Safety rule

日時・VRChat関連性・開催/募集の実体を証拠から確定できない候補は、LLMが推測してacceptしない。
`needs_more_evidence` または `reject` とし、根拠のない補完を禁止する。
