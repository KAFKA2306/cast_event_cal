# VRChat Event Calendar Aggregator

**リポジトリ:** https://github.com/KAFKA2306/cast_event_cal

複数の公開情報源からVRChatイベントを取得し、日時、主催者、会場、状態を正規化して、JSON、iCalendar、Web表示へ変換するプロジェクトです。

タイトルが似ているだけでは同一イベントとして統合せず、主催者、出典識別子、日時、会場またはワールドを照合します。

## できること

- 公開されているVRChatイベント情報を取得
- タイムゾーンを保持して日時を正規化
- 単発イベントと繰り返しイベントを整理
- 重複、変更、中止、期限切れを区別
- JSONデータを生成
- iCalendar形式を生成
- Web表示用コンテンツを更新

## データ処理の流れ

```text
主催者・イベント媒体の公開情報
  → 元レコードと取得時刻を保存
  → 主催者・イベントを同定
  → 日時・タイムゾーン・繰り返しを正規化
  → 重複・変更・中止・期限切れを判定
  → JSON・iCalendar・Web表示を生成
```

タイムゾーン、出典、主催者が欠けるレコードは、推測で確定せず`flag_conflict`として扱います。

機械可読な定義:

- [プロジェクト・オントロジー](ontology/project.yaml)
- [共通因果・証拠オントロジー](https://github.com/KAFKA2306/know/blob/main/ontology/causal-evidence-core.yaml)

## 必要環境

- Python 3.9以上
- `requirements.txt`の依存関係
- `config/main_config.yaml`
- `config/scraping_targets.yaml`

## セットアップ

Linux / macOS:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 実行

```bash
python main_executor.py
```

生成される各形式は、同じ正規化イベントレコードを入力とし、出典、取得時刻、変換規則を追跡できる状態にします。

## 運用時の注意

- イベント日時は必ずタイムゾーン付きで扱う
- 主催者による変更・中止告知を過去データより優先する
- 繰り返し予定から生成した回と、主催者が個別告知した回を区別する
- 非公開、参加条件付き、招待制イベントを公開イベントとして断定しない
- 取得元の利用規約とアクセス頻度制限に従う

## 公開状態

README更新時点で、このリポジトリ固有の公開カレンダーURLは確認できていません。公開先を設定した場合は、完全なURLをREADME冒頭へ追加してください。

## ライセンス

MIT

**README最終監査:** 2026-08-01
