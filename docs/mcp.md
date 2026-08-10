# Event MCP

`cast_event_cal` はVRChatイベントデータの正本です。MCPは `public/*.json` に対するread-only adapterであり、取得・分類・ontology matchingを再実装しません。

## Start

```bash
python -m pip install -e '.[mcp]'
cast-event-cal-mcp
```

既定は `127.0.0.1:8011` のStreamable HTTPです。

## Tools

- `search_events`
- `get_event`
- `get_tonight_events`
- `get_series`
- `get_source_health`
- `get_classification_audit`
- `get_ontology`
- `get_data_quality`
- `get_methodology`

検索系は `limit <= 100` と `offset` を要求し、大量candidate historyを無制限に返しません。

## Provenance

イベントtoolは、公開event recordを変更せず `provenance` を追加します。存在する範囲で以下を返します。

- canonical ID
- public schema version
- event start
- source-created / first-seen / last-seen timestamps
- snapshot generated timestamp
- source type / source ID / source URL
- classification rule / classification evidence
- ontology/series ID
- freshness seconds
- missing fieldの `null_reasons`

公開eventに記録されていない観測時刻やseries IDを推測生成しません。

## Tonight replay

`get_tonight_events(date_jst='YYYY-MM-DD')` は `starts_at` をAsia/Tokyoへ変換し、指定JST暦日だけを返します。明示日を渡せるため、相対的な「今夜」を後日再現できます。

## Fail-close

- event ID重複はdata-quality contract違反
- `health.json:event_count` と `events.json` 件数不一致はcontract違反
- ontology ambiguous countは0を要求
- ontology matching policyは `ambiguous_match_action=reject`
- LLMはcanonical classifierにしない
- deploy repo `KAFKA2306/vrc_cast_event_calender` へ分類ロジックを複製しない
- EDINET DBは使用しない (`edinetdb_mode=not_applicable`)

## Tests

`tests/test_mcp_contract.py` はMCP tool discovery、public events parity、event provenance、JST replay、human-curated ontology、duplicate/ambiguity gate、canonical/deploy boundaryを検証します。
