# VRChat Event Calendar Aggregator

複数の公開情報源からVRChatイベントを取得し、正規化されたJSON、iCalendar、Web表示へ変換するプロジェクトです。

## 因果・証拠オントロジー

上位システムは `VRChatEventAggregationSystem` です。

```text
主催者・イベント媒体の公開情報
→ 出典レコード取得
→ 主催者・イベント同定
→ タイムゾーン・日時・繰返し正規化
→ 重複／変更／中止／期限切れ判定
→ JSON・iCalendar・Web公開
```

タイトルが似ているだけではイベントを統合しません。主催者、出典識別子、日時、会場またはワールドの証拠を使って同一性を判定します。タイムゾーン、出典、主催者が欠ける場合は `flag_conflict` とし、中止・変更・期限切れを明示します。

- [プロジェクト・オントロジー](ontology/project.yaml)
- [共通因果・証拠オントロジー](https://github.com/KAFKA2306/know/blob/main/ontology/causal-evidence-core.yaml)

## 主な機能

- 公開VRChatイベント情報の集約
- タイムゾーンを保持した日時正規化
- 重複、変更、中止、期限切れの状態管理
- iCalendar生成
- JSON API生成
- Webコンテンツ更新

## 必要環境

- Python 3.9以上
- `requirements.txt` の依存関係
- `config/main_config.yaml`
- `config/scraping_targets.yaml`

## セットアップ

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windowsでは `venv\Scripts\activate` を使用します。

## 実行

```bash
python main_executor.py
```

各出力は同一の正規化イベントレコードから生成し、出典・取得時刻・変換規則を追跡可能にします。

## ライセンス

MIT