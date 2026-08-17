# cast_event_cal — VRChat Event Intelligence

[![CI](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/ci.yml/badge.svg)](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/ci.yml)
[![Update calendar data](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/update-calendar-v2.yml/badge.svg)](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/update-calendar-v2.yml)
[![Deploy GitHub Pages](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/deploy-pages.yml)
[![Public feed integrity](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/public-feed-integrity.yml/badge.svg)](https://github.com/KAFKA2306/cast_event_cal/actions/workflows/public-feed-integrity.yml)

**告知を見つけただけでは、参加できるイベント情報にはならない。**

日時、参加方法、募集締切、公式リンク、投稿時点は別々に書かれます。古い「本日開催」を検索日へ読み替えたり、商品販売をイベントとして採用したりすると、カレンダーは便利になるほど誤情報も増やします。

`cast_event_cal` は、公開イベント・定期集会・募集締切を **出典・観測時刻・採否理由を残したまま正規化し、JSON / iCalendar / Web UIへ変換して公開する正本repository** です。

- 公開カレンダー: https://kafka2306.github.io/cast_event_cal/
- 今夜のイベント: https://kafka2306.github.io/cast_event_cal/tonight/
- JSON: https://kafka2306.github.io/cast_event_cal/events.json
- iCalendar: https://kafka2306.github.io/cast_event_cal/calendar.ics

収集・正規化・分類・ontology・canonical snapshot生成・GitHub Pages配信をこのrepositoryで完結します。旧 `KAFKA2306/vrc_cast_event_calender` は既存URL互換性を確認した後にarchiveします。

## Vision

VRChatイベント探しを「SNSを巡回して、それっぽい投稿を自分で解釈する作業」から、**今後参加できる候補を出典付きで比較し、主催者の公式情報へ短く到達できる体験**へ変えます。

利用者に届けたいのは件数ではなく、次の判断材料です。

- いつ開催されるか
- どう参加するか
- 単発か定期か
- どの告知を根拠にしたか
- 情報がいつ観測されたか
- 自動分類がなぜ採用・棄却したか
- 公式Group / X / Web等へ戻れるか

## Design philosophy

- **Evidence before coverage.** 候補数を増やすために日時・参加方法・event性を推測しない。
- **Relative time belongs to the source post.** `本日` / `明日` / 曜日は収集日ではなく投稿時刻を基準に解釈する。
- **Reject is a first-class result.** 棄却理由を捨てず、classifier改善と回帰検証に使う。
- **Ontology does not guess.** alias / organizer / required patternが不足・競合する場合は`ambiguous`へ隔離する。
- **Validate before publish.** 収集・分類・生成を検証してから同じrepositoryの公開artifactを配信する。
- **No hidden LLM judgment in daily classification.** 日常運用の採否は決定論的なPython処理で再実行可能にする。
- **Official source wins.** calendarは発見を助けるが、最終的な日時・参加条件は主催者の最新公式情報を優先する。

## Why / 差別化

一般的なevent aggregatorでは、「見つかった投稿を一覧にする」ことが価値になりがちです。本repoはその一歩手前、**投稿をeventとして採用してよいかを説明できること**を中心に置きます。

差別化はYahoo検索、X API、ontology、ICS自体ではありません。

- source post IDと観測履歴を残す
- 相対日時をsource投稿時刻から復元する
- 商品販売・プレゼント応募・過去eventを理由付きで落とす
- 高反応投稿でもevent evidenceがなければ採用しない
- classification rule変更後に過去候補を再判定できる
- 正本dataから生成した公開artifactをproductionで再検証する

ことで、**「なぜ載っている／載っていない」を後から説明できるcalendar**を作ります。

## Canonical flow

```text
recurring definitions
VRChat official calendar
X API observations
Yahoo realtime search shards
        │
        ▼
source identity / observed time
        │
        ▼
normalization + deterministic classification
        │
        ├─ accepted event
        └─ rejected candidate + reason
        │
        ▼
deduplication + ontology match
        │
        ▼
public/ canonical snapshot
        │
        ▼
GitHub Pages
```

## Canonical data

- `data/recurring_events.json` — 定期series
- `data/one_off_events.json` — 単発event
- `data/discovered_events.json` — VRChat公式calendar
- `data/x_events.json` — X API採用結果
- `data/yahoo_realtime_candidates.json` — Yahoo candidate ledger
- `data/yahoo_realtime_events.json` — Yahoo採用結果
- `data/yahoo_realtime_rejected.json` — 棄却record
- `data/yahoo_realtime_health.json` — source health
- `config/event_ontology.json` — event ontology
- `config/yahoo_query_terms.json` — search shard vocabulary

Public artifact:

- `public/events.json`
- `public/calendar.ics`
- `public/health.json`
- `public/yahoo-candidate-history.json`
- `public/yahoo-classifier-audit.json`
- `public/event-ontology.json`
- `public/ontology-match-audit.json`
- `public/tonight/`

## Candidate ledger / classification

単一queryの上位結果だけに依存せず、開催・参加・JOIN・店舗型・活動・募集・日時・noise監査等のsearch shardをローテーションします。candidateは検索画面から消えても再評価できるよう履歴を保持します。

```text
query shards
  → status_id dedupe
  → source_created_at restore
  → observation history
  → latest deterministic rules
  → accept / reject + reason
  → classifier audit
```

`本日`、`今日`、`明日`は再処理日ではなく`source_created_at`を基準に解釈します。投稿日時を復元できない場合だけ明示fallbackを使い、過去になったeventは`past_event_now`として棄却します。

fail-closeの代表例:

- retweet数が取得できない → 採用しない
- 商品販売 / 無料配布 / プレゼントだけ → 採用しない
- follow / RP / likeだけが参加方法 → event参加とは扱わない
- 日時欠損 → 採用しない
- 告知月と明示日付が矛盾 → 採用しない
- 過去event → 採用しない
- ambiguous ontology match → 公開しない

rule変更時は回帰testとclassifier auditの両方へ固定します。

## Event ontology

`config/event_ontology.json` は、series / organizer / alias / official link / participation method / format / audienceを管理する機械可読辞書です。

matchは単なるfuzzy searchでは成立しません。alias exact match、またはofficial organizer + required patternsが必要です。競合時は補完せず`ambiguous`です。

## Automation

`.github/workflows/update-calendar-v2.yml` は毎日05:17 JST、手動、主要logic変更時に起動します。

主な流れ:

1. recurring seriesを未来へ展開
2. official calendar取得
3. X candidates分類
4. Yahoo shards取得
5. candidate ledger統合
6. source投稿時刻を基準に再分類
7. UTC正規化・dedupe
8. ontology enrichment
9. JSON / ICS / responsive UI生成
10. quality gate
11. canonical差分commit
12. 同repositoryのGitHub Pagesへ配信
13. production HTML / JSON / ICS / tonightをread-back

日常分類ではLLM判定を使用しません。

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
ruff check cast_event_cal scripts tests
pytest
cast-event-cal validate
python scripts/materialize_events.py
cast-event-cal run --strict
python scripts/render_frontend.py
python -m http.server 8000 --directory public
```

## Quality gate

- 日時・終了時刻・隔週基準を推測しない
- source failureで正常cacheを空dataへ上書きしない
- HTML構造不明なら候補を通さない
- eventと商品販売を混ぜない
- relative dateを収集日基準で復活させない
- ontology ambiguityを公開しない
- classification変更へregression testを追加する
- Python 3.11 / 3.12 / 3.13 CI
- production HTML / JSON / candidate ledger / audit / ontologyをread-backする

## Secrets

- `X_BEARER_TOKEN`
- `VRCHAT_AUTH_COOKIE`

Yahoo realtime searchにはsecretを使いません。

## Repository boundary

```text
cast_event_cal
  data / collection / classification / ontology
        ↓
  public/ HTML / JSON / ICS
        ↓
  GitHub Pages / production verification
```

MCPや別UIを増やす場合も、正本dataとclassification logicを二重実装しません。

## Done

成功指標はcandidate数や公開event数ではありません。

**利用者が参加候補へ早く到達でき、運営側は各eventについて「どの投稿を、いつ観測し、なぜ採用し、どの公式情報へ戻れるか」を説明できること**をDoneとします。

## License

MIT
