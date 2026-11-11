# cast_event_cal Agent Contract

## 開始・正本
この文書と、変更対象に必要な正本コード・データ・監査結果だけを読む。Issue、履歴、アーカイブを一括で事前読込しない。作業は目的・変更可能範囲・完了条件・証拠・次の一手を既存Issue/PRの単一worklineに記録する。

このrepoが収集、正規化、決定論的分類、候補の採否と理由、イベントID、開催回の重複排除、ontology、`public/` 生成を所有する。`KAFKA2306/vrc_cast_event_calender` は配信のみで正本を複製しない。

優先順位: 現在の依頼 > 正本コード/データ/監査 > 一次出典 > exact-head検証 > 現行設計 > Issue/PR履歴 > 推測。

## 証拠と安全
事実を `VERIFIED` / `OBSERVED` / `INFERRED` / `UNVERIFIED` に分け、未確認事項を事実化しない。

- 日時・参加方法・指標・主催者ID・投稿時刻・ontology一致を捏造しない。相対日時は収集日でなく投稿時刻から解決する。
- 出典の矛盾、証拠不足、権限未確認は理由を記録して保留・棄却する。LLMだけで日常の採否を確定しない。
- 取得失敗で正常なキャッシュを空/不完全データへ上書きしない。公開投影より正本観測を優先する。
- Yahooの権限は利用者の申告と権利者の独立確認を区別し、fail-closedを維持する。

## 変更・検証
一つの結果に一つの正本処理・監査・worklineを使う。重複する経路は参照を検査してから削除する（DELETE > MERGE > REPLACE > ADD）。余計なCI・テスト・台帳を増やさない。

関連範囲の最小検証から始め、実際に実行しなかったコマンドをPASSとしない。標準例:

```bash
ruff check cast_event_cal scripts tests main_executor.py
pytest -q
python scripts/materialize_events.py
python main_executor.py run --strict
python scripts/render_frontend.py
```

PRの変更HEADと必須条件を確認して統合する。公開変更では統合後の本番URL・JSON・監査・snapshotを別途確認する。Actions成功だけで本番成功と断定しない。

## Issue管理
新規Issueは実在する未解決の問題、明確な所有者と完了条件、AIが実行できる次の作業、既存Issueとの非重複を満たす場合だけ作成する。

- 重複は正本Issueに固有要件を残して `duplicate` で閉じる。
- 根拠のない案、解消済み案、効果不明の保守案件は理由・再開条件を残し `not_planned` で閉じる。
- 第三者の許諾・契約・認証情報・外部アカウント設定・人間判断だけが残る案件も、AI実行可能な作業が尽きれば再開条件を残し `not_planned` で閉じる。
- 本番障害、検証済みの安全性・データ欠陥、利用者が優先指定した仕事は保持。Issueを閉じても安全ガードを解除したり許諾済みを偽装したりしない。

終了時は修正対象、正本の確認結果、完了/未完了、必要な次の一手を短く報告する。ブロックが残れば既存Issue/PRに証拠と再開条件を保存する。

## CI予算
PRではPython 3.12の単一lint/testジョブを基本とする。Python多バージョン行列、更新のたびの重複pytest、専用監査ワークフローの再追加は禁止。取得権限、公開snapshot、競合書込み、本番安全性は既存の本番ジョブ内で保護する。新規ゲートは独自の失敗検知・責任者・費用・実行頻度を明示し、既存処理への統合を優先する。
