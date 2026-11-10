# Yahoo!リアルタイム検索：発見ロジックの過去パターン全面監査

作成日：2026-11-11 JST  
観測時点：2026-11-10 11:14:58 UTC（20:14:58 JST）  
対象：`KAFKA2306/cast_event_cal` のYahoo検索 → 投稿抽出 → イベント分類 → 日時解決 → 同一イベント照合 → 掲載 → 改善フィードバック。

## 結論（VERIFIED / INFERREDを区別）

- **VERIFIED**：現存5,000候補の採用は160件（3.2%）。最大の棄却理由は `missing_datetime` 4,134件（82.68%）。ただし棄却4,134件＝発見漏れ4,134イベントではない。
- **VERIFIED**：`missing_datetime` を調べると **668件が不完全/曖昧日時、93件が未安全展開の定期開催、17件が解析不能候補**。この778件は「追加証拠または規則改善で再評価する母集団」であって、正解777件などとは主張できない。
- **VERIFIED**：過去16時点のYahoo候補履歴では、異なる投稿ID **17,735件**、そのうちいずれかの時点で一度は採用された投稿ID **1,700件**。現存5,000件だけを母集団とする調査では過去を代表できない。
- **VERIFIED**：Yahoo LLMレビューキューは **1,224件pending、判定済みresolutionsは0件**（キュー生成時点2026-11-10 02:54:48 UTC）。レビュー結果を継続的なルール改良に返す閉ループは、記録上まだ実績がない。
- **VERIFIED**：`public/yahoo-query-yield-audit.json` の196クエリは productive 6、insufficient-evidence 185、redundant 5。採用率・exclusive yieldは内部classifier基準で、独立の正解照合ではない。
- **INFERRED**：改善の優先順位は「独立goldによる発見網羅性の測定」→「日時・連続開催・募集/抽選などの型別修正」→「レポートをルールに戻す」→「クエリの再配分」。現在のデータだけではサイト全体のrecall率を算出できない。

### 検証に使った正本

- [Yahoo候補履歴（現存5,000）](../public/yahoo-candidate-history.json)、[classifier audit](../public/yahoo-classifier-audit.json)、[publishability audit](../public/yahoo-publishability-audit.json)、[query yield](../public/yahoo-query-yield-audit.json)
- [検索語設定](../config/yahoo_query_terms.json)、[Yahoo収集](../scripts/collect_yahoo_corpus.py)、[HTML抽出と日時parser](../scripts/fetch_yahoo_realtime.py)、[過去再分類](../scripts/reclassify_yahoo_archive.py)、[同一イベント証拠照合](../scripts/yahoo_evidence_graph.py)
- [レビューキュー](../data/yahoo_llm_review_queue.json)、[レビュー判定済み](../data/yahoo_llm_review_resolutions.json)、[レビュー監査](../public/yahoo-llm-review-queue-audit.json)
- [9月29日 best-1000 実験](../public/yahoo-best-1000-audit.json)、[11月10日 ablation](../public/yahoo-query-ablation.json)、[クエリエキスパート](../public/yahoo-query-expert-model.json)、[独立gold](../config/coverage_gold.json)、[発見評価コード](../scripts/audit_coverage.py)
- [本番更新成功の実行](https://github.com/KAFKA2306/cast_event_cal/actions/runs/42805583423)、[scorecard](../public/yahoo-autonomy-scorecard.json)

## 1. 過去の16スナップショット：現存履歴だけでは不十分

`public/yahoo-candidate-history.json` の過去版をGitHubのコミットから抽出し、`status_id` 単位で重複除去した。観測時点はほぼ週次＋月末補完。各スナップショットの accepted は **その時点で採用判定の候補投稿数** であり、実際のサイト掲載イベント数でも、新規発見数でもない。

| スナップショット | 候補件数 | その時点の採用 | 16時点の累積ユニーク新規ID |
| --- | ---: | ---: | ---: |
| 08/09 | 3,745 | 589 | 3,745 |
| 08/16 | 4,860 | 753 | 1,115 |
| 08/20（08/23時点の直近版） | 5,000 | 334 | 622 |
| 08/31 | 5,000 | 80 | 888 |
| 09/07 | 5,000 | 65 | 952 |
| 09/14 | 5,000 | 65 | 898 |
| 09/21 | 5,000 | 159 | 1,105 |
| 09/26（09/28時点の直近版） | 5,000 | 71 | 385 |
| 09/30 | 5,000 | 122 | 619 |
| 10/07 | 5,000 | 94 | 1,412 |
| 10/14 | 5,000 | 79 | 1,138 |
| 10/21 | 5,000 | 85 | 1,158 |
| 10/28 | 5,000 | 81 | 1,259 |
| 10/31 | 5,000 | 146 | 575 |
| 11/04 | 5,000 | 81 | 729 |
| 11/10 | 5,000 | 160 | 1,135 |

- **合計17,735異なる投稿ID**、16時点のどこかで一度でも採用された投稿ID **1,700**、一度も採用されなかった投稿ID **16,035**。
- 同じ投稿IDで、観測した `last_reason` が変化したもの **162件**。過去に採用された後、最後の観測時点では棄却だったもの **27件**。過去のイベントが期限切れになることもあるため、これらの数だけで「誤分類」と断定しない。
- 08/31と11/10の5,000候補には **共通IDが0件**。10/31と11/10には **3,147件**共通。5,000件上限は保持対象を大きく入れ替える。
- 同一IDのスナップショット間推移では `missing_datetime→accepted` 7、`missing_event_marker→accepted` 3、`giveaway_only→accepted` 3を観測。ただし16時点間の部分観測であり、全改良履歴ではない。
- `retention_days=365` と設定されていても、**`maximum_candidates=5000` が先に実効保存範囲を限定**しうる。古い候補がない＝当時探索されなかった、ではない。

監査対象GitHubコミット（過去版を再現可能）：
`1a2c5247`（08/09）、`24bb9f65`（08/16）、`b8443ea5`（08/20）、`266ccb01`（08/31）、`7f5b36f0`（09/07）、`4494136e`（09/14）、`0e7b7207`（09/21）、`6ac94f14`（09/26）、`df9520b1`（09/30）、`2de506de`（10/07）、`a0e1d69a`（10/14）、`a32d81c4`（10/21）、`6e8e9eae`（10/28）、`aa3a4e73`（10/31）、`01c6293d`（11/04）、`63754b69`（11/10）。

**範囲の限界**：16時点に存在しなかった短命候補や、そもそもYahoo検索が返さなかった投稿は含められない。「観測済みの分類・検索パターンの完全整理」であり、ネット上のVRChatイベント全件の完全列挙ではない。

## 2. 現存5,000件の全分類結果（相互排他的）

| 機械判定（last_reason） | 件数 | 解釈 |
| --- | ---: | --- |
| accepted | 160 | その時点で採用された候補投稿 |
| missing_datetime | 4,134 | 日時が確定できず掲載不可 |
| missing_event_marker | 380 | イベントとして認識できない |
| giveaway_only | 228 | 景品/抽選が主体と判定 |
| product_only | 84 | 商品/販売が主体と判定 |
| missing_participation_method | 8 | 私的インスタンス等で参加方法不明 |
| too_far_future_now | 5 | 日時が許容範囲外 |
| not_vrchat | 1 | VRChatとの関連性を確認できない |
| **合計** | **5,000** | 各候補は一度だけカウント |

`missing_datetime` 4,134件の内部決定を完全分解：

| publishability 判定 | 件数 | 主な課題 |
| --- | ---: | --- |
| no_datetime_evidence | 1,946 | 本文から日時根拠なし。告知画像・外部リンク・雑談などが混在する可能性 |
| non_event / non_event_commerce / non_event_personal | 1,114 | 非イベントと判定。1,114件の救済を目標にしない |
| partial_datetime / ambiguous_datetime | **668** | 日付または時刻が曖昧。追加証拠照合対象 |
| past_event_or_report | 296 | 過去開催、参加報告など |
| recurring_event | **93** | 日時を安全に繰り返し展開できない |
| resolvable_event_candidate | **17** | 既存parser未対応・不安全な表現 |
| **合計** | **4,134** | これは内部ラベルで、正解goldではない |

さらに `resolution_blocker` 全13ラベルの件数：
`no_datetime_evidence` 1,946／`non_event` 820／`no_peer_evidence` 371／`past_event_or_report` 296／`missing_or_conflicting_date` 190／`non_event_commerce` 159／`non_event_personal` 135／`recurrence_pattern_unsupported_or_unsafe` 93／`missing_or_conflicting_clock` 58／`no_strong_event_signal` 35／`datetime_parser_unsupported_or_unsafe` 17／`out_of_publication_window` 12／`conflicting_fingerprint_resolution` 2。合計4,134。

## 3. 検索パターンと落とし穴の全系統

### 検索語の系統

`config/yahoo_query_terms.json` に固定base式5、系統別語句138（core16、access15、venues13、activities32、communities21、recruitment10、commerce_noise14、temporal_audit17）。`collect_yahoo_corpus.py` の動的選択では、日次定数18検索に根拠探索12検索などを組み合わせ、最新本番は **37検索中37成功**。

| 系統 | 代表表現 | 見落とす型 |
| --- | --- | --- |
| core | イベント告知、集会、営業、OPEN、公演 | 固有イベント名だけの告知、語彙違い |
| access | JOIN、リクイン、Group+、フレンド申請 | リンク先や画像にしか参加方法がない告知 |
| venues | カフェ、バー、クラブ、居酒屋 | 営業という語を使わない集い |
| activities | DJ、音楽、朗読、謎解き、ボドゲ、TRPG、ツアー | 略称、英語固有名詞、シリーズ名 |
| communities | 学術、技術、言語交流、学校、開発者 | 定例名・ハッシュタグだけの告知 |
| recruitment | キャスト、スタッフ、演者、テスター、締切 | 応募開始と本開催を混同、募集日時と開催日時を取り違え |
| commerce_noise | BOOTH、販売、セール、配布、景品 | 商品紹介とイベント告知が同じ文章にある |
| temporal_audit | 今日、明日、今夜、曜日、21時 | 本文に開始時刻が無い、投稿時刻から解釈が必要 |

条件の問題：
1. `VRChat` / `VRC` といった語が本文に無い告知は、そもそも検索・後段の関連性判定に入らないことがある。母集団に存在しないため **現在の候補履歴から件数は測れない**。
2. 検索結果のtop-K（実験では40件）、検索結果の時刻依存、重複投稿によるランキング占有がある。候補IDの数は検索網羅率ではない。
3. [query yield audit](../public/yahoo-query-yield-audit.json) の196クエリではproductive6・insufficient-evidence185・redundant5。唯一採用候補の検索帰属 `unique_only_accepted` 合計は13だが、これは**その監査コーパス内の排他的発見**で、初掲載13件を保証しない。
4. [2026-09-29 best-1000](../public/yahoo-best-1000-audit.json) では90検索で1,000候補、採用44、既存台帳にない新規採用18。古い分類では `retweet_below_threshold` 474件。現在の採用160件中65件はリポスト0〜2件であり、過去の3RT閾値をそのまま再導入すると失う可能性がある。測定条件が異なるため、この数を前後のrecall改善率とみなさない。
5. [query-expert-model](../public/yahoo-query-expert-model.json) は`status=insufficient_evidence`、accepted universe607、ensemble positive coverage0.892916で、推奨クエリ0件。自動最適化が確立しているとの判断はできない。

### 時刻・日付・意味の失敗パターン（重複あり）

| 型 | 現状 | 例・検証対象 |
| --- | --- | --- |
| 明示日付＋直後の時計 | 通ることが多い | `11/13(金) 21:30` |
| 日付と時計の間にイベント名/曜日英語が挟まる | parserが落とす | [2026/11/11 (wed) ... OPEN 19:30 / START 20:00](https://x.com/i/web/status/2119392998828212268) |
| `14日(土) 22:00`・曜日ありの日だけ | parser未対応がある | [SCP集会](https://x.com/i/web/status/2119454415459602742) |
| `今週木土18時`・曜日を二つ含む | 複数開催日を確定できない | [再演告知](https://x.com/i/web/status/2117135601535471946) |
| `今日`、`明日`、`今夜`、`このあと` | 投稿時刻アンカーが必要。発見が遅れると開催が終了する | relative date / source timestamp |
| `OPEN` と `START`、開場/開演の二時計 | 開始対象を間違えうる | 説明本文より開場/開演を区別 |
| `23:00-24:00`・`24時/25時` | 日跨ぎ・24時表記 | 日付を勝手に補正しない |
| 毎週・隔週・第N曜日、シリーズ回数 | 93件が未安全展開 | 再帰ルールには期間・時刻・中止情報が必要 |
| 日付だけ・終日/会期 | 開始時計を捏造できない | 大型展示会、募集締切、ライブ開催期間 |
| 投稿が出演/応募/開催を複数併記 | 日付を取り違えやすい | `応募締切`、`本公演`、`入場時刻` は別fact |
| JST/UTC/PST等が混在 | 外国時刻をJSTと決め打ちしない安全策 | 明示JST優先、未確定は保留 |
| リプライ/引用/同一主催者の他投稿に日時 | `no_peer_evidence` 371件 | 関連投稿のsame-event照合。独立証拠なしでは保留 |
| 画像・外部ページだけに日時 | テキスト抽出で漏れる | 画像/公式ページにあるかは、現状の候補本文だけでは未検証 |
| 中止・延期・変更・参加報告 | 過去時刻でも掲載すべきでない | 中止告知を追加イベントにしない |
| 固有名詞だけのイベント名 | `missing_event_marker` の原因 | 言語交流・茶道・音楽の固有名のように「開催」を使わない |

**具体的に見える精度課題**：`missing_event_marker` 380件中167件は単純な正規表現で「日付らしい文字列と時刻らしい文字列」が両方見つかる。ただし中止・配信・過去報告も含むため **167件が真の取り逃しとは限らない**。例として[DJイベントの日時・Group Onlyが明記された投稿](https://x.com/i/web/status/2119754909415625043)が残っている。

**混同による取り逃し**：`giveaway_only` 228件には、イベント参加を事前抽選やフォロー/リポストで受け付ける実イベント告知も混在する。例：[抽選付きVRC接客イベント](https://x.com/i/web/status/2119893936047300885)。`product_only` 84件にも、商品名やアバターを伴う実イベント案内らしい候補がある。例：[接客カフェバーの告知](https://x.com/i/web/status/2120053857858572382)。逆に、景品抽選・セールだけを強引にイベント化すると誤掲載が増える。

## 4. 収集速度、証拠、掲載の品質

- 現存5,000候補のうち、元の投稿時刻から `first_seen_at` まで計算可能で非負の4,995件では、**中央値4.98時間、90パーセンタイル102.19時間**。検索ヒットから「サイト掲載」までの時間ではなく、観測開始までの遅れである。
- `publishability` の `no_peer_evidence` は371件。現行のpeer evidenceを利用した新たなcorroborated materializationは、[publishability audit](../public/yahoo-publishability-audit.json) で **0件**。
- classifier監査は `suspicious_accepted_commerce` を24件抽出。**24件の誤掲載が確定したという意味ではない**。正解原典との照合を要する。
- 最新の本番差分 `public/yahoo-autonomy-scorecard.json` はYahoo由来occurrence **追加9、消失4、消失理由 `unknown=4`、純増5**。終了・重複・履歴上限・日時再評価のいずれかはまだ特定できない。
- 関連イベントの日時をほかの投稿から採る場合、`event_fingerprints` / 主催 / 引用・返信 / 公式URL / グループなどを近接時刻の証拠としてチェックする。合致しない投稿の時刻流用、推測日時の採用は禁じる。

## 5. フィードバックが閉じていない

[LLMレビューキュー](../data/yahoo_llm_review_queue.json)（2026-11-10 02:54:48 UTC）：
- pending **1,224件**、priority high **481件**、medium371、normal372。
- `ambiguous_rejection` **1,209件**、`possible_false_positive` **15件**。
- machine_reason は `missing_datetime` **1,046件**、`missing_event_marker` **158件**、`missing_participation_method` **5件**、`suspicious_accepted_commerce` **15件**。
- [review resolutions](../data/yahoo_llm_review_resolutions.json) は **0件**。レビューはAIに推測をさせる処理ではなく、候補の出典/時刻の再調査→`accept`/`reject`/`needs_more_evidence`→再利用可能なルール候補の検証、を目的とする。

## 6. 未観測の真の取り逃しを測る仕組みの不足

独立の[coverage gold](../config/coverage_gold.json) は **1件**だけ。これではサイト全体のイベント発見率（recall）を示せない。コードが出力する`accepted_count`は自分の判定に合った投稿数であり、precisionでもrecallでもない。

新しいゴールド集合は、**Yahoo検索結果や本サイトの掲載結果を参照せず**、独立したイベント主催者・許可済み公式カレンダー等の日時・出典から構成する。少なくとも以下を層別し、検証時刻に開催期間内だったかも固定する：

1. 音楽/DJ、接客店、集会、学術、ゲーム、マダミス、展示、ワールドツアー、募集、会期型、定期開催、海外言語の各型
2. 日付が文中にある・画像のみ・引用/返信・固有名詞のみ・複数開催日・時刻がない・延期・中止
3. リポスト0〜2/3〜9/10以上、主催者と紹介者、長文/短文
4. `search_not_retrieved` → `retrieved_but_rejected` → `accepted_but_not_published` → `published_correct` と段階別に計測

この独立ゴールドが成立するまで、**「発見率何%」という断定は不可**。

## 7. 次の実装優先順位と採否基準

| 優先 | 現在の所有Issue | 具体的な改善 | 合格基準 |
| --- | --- | --- | --- |
| 1 | [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190) | 独立goldを型別作成し、検索前・検索後・掲載前の損失を区分。上位検索の排他的実掲載を計測 | 正しい新規掲載occurrence数が増え、goldの漏れを悪化させない |
| 2 | [#196](https://github.com/KAFKA2306/cast_event_cal/issues/196) | 17 parser候補から実イベントだけを独立確認。英語曜日を挟む日付、`日(土)`、OPEN/START、24時などの安全な表記を回帰テストで拡張 | 誤日付0、独立正解がある実イベントのみ昇格 |
| 3 | [#196](https://github.com/KAFKA2306/cast_event_cal/issues/196) | 668不完全日時・93定期開催を発信元の確かな日時証拠と照合 | 推測でなく証拠付きで新規公開、再現可能なsource provenance |
| 4 | [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190) | `missing_event_marker`・抽選・商品併記のfalse-negativeと実イベント以外のnoiseを分ける | 固定コーパスでreplayしprecisionを維持 |
| 5 | [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190) | 1,224件のレビューキューを重複なく処理可能な順に評価し、一般化したルールだけ自動採用 | reviewed/resolved・誤受理・改善効果が監査可能 |
| 6 | [#190](https://github.com/KAFKA2306/cast_event_cal/issues/190) | 履歴の上限5,000による候補退出を記録し、新規発見・過去再分類・消失理由を分ける | `unknown_removals`が正当な根拠で説明される |

**安全境界**：現時点では観測・再評価の結果を記録するだけ。未確認日時を自動で捏造せず、正しいイベントの消失を黙って許容せず、検索リクエスト増量は独立の利得測定後に検討する。

## 8. この調査の精度と未検証事項

- VERIFIED：現在の履歴全5,000件の `last_reason` / `publishability_decision` / `resolution_blocker` は全件集計し、件数が一致することを確認。
- VERIFIED：GitHubに存在する16旧版スナップショットの投稿IDを通算し、17,735ユニーク、1,700一度でも採用と計測。
- VERIFIED：196 query metrics、September best-1000、LLMキュー1,224・解決0、gold1件を読み出し。
- OBSERVED：主要な false-negative と疑われる現行投稿テキストの例を確認。実際の現地開催・現在の主催告知との差分を一次原典で完全検証したわけではない。
- UNVERIFIED：16時点の間にだけ存在した全候補、Yahoo検索で一度も返らなかった全イベント、投稿にない画像内の日時、現行カレンダー全体の真のrecall、消失4件の確定原因。

**結論：検索語を増やすより先に、取り逃しの正解集合を作り、現在すでに取得済みの候補を安全に掲載へ昇格させる評価・改善ループを閉じる必要がある。**
