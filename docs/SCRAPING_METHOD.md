## Twitter(X) 自動化・スクレイピングシステム 詳細ドキュメント

### 1. はじめに

#### 1.1 目的
このドキュメントは、PythonとPlaywrightを使用してTwitter(X)のログイン自動化、ツイート検索結果、およびリストメンバー情報を収集するシステムの詳細な解説を提供します。特に、頻繁なUI変更に対応するための「適応型セレクター」の実装、自動化検出の回避策、エラーハンドリング、デバッグ手法に焦点を当てています。

#### 1.2 対象読者
- PythonとPlaywrightを使用したWebスクレイピング・自動化に興味がある開発者
- Twitter(X)のUI変更により既存のスクリプトが動作しなくなった開発者
- 堅牢なWebスクレイピングシステムの構築方法を学びたい方

#### 1.3 前提知識
- Pythonプログラミングの基本知識
- Web技術（HTML, CSSセレクター, JavaScript）の基本知識
- Playwrightまたは類似のブラウザ自動化ツールの使用経験（あれば尚可）

---

### 2. システム概要

#### 2.1 全体の目的
このシステムは、以下の自動化タスクを実行します。
- Twitter(X)への自動ログイン（2段階認証対応）
- 指定された検索クエリに基づくツイートの収集
- 指定されたTwitterリストのメンバープロフィール情報の収集
- 収集したデータの検証とJSON形式での保存
- キャッシュによる重複取得の防止

#### 2.2 使用技術
- **プログラミング言語**: Python 3.x
- **ブラウザ自動化**: Playwright (非同期API)
- **要素特定**: 適応型セレクター（カスタム実装）、Playwright推奨ロケーター (`get_by_role`, `get_by_text`, `get_by_test_id`)
- **データ形式**: JSON

#### 2.3 主な機能
- **自動化検出回避**: User-Agent偽装、`navigator.webdriver`属性の隠蔽、その他のブラウザプロパティ調整により、自動化ボットとして検出されにくくします。
- **適応型セレクター**: 事前に定義された複数の属性（`name`, `placeholder`, `aria-label`など）や、テキスト、ロール、`data-testid`を組み合わせて要素を探索し、HTML構造の変更に対する耐性を高めます。
- **段階的ログインフロー**: ユーザー名入力 → 次へ → (追加認証) → パスワード入力 → ログイン → (2FA) の各ステップを確実に実行し、ステップ間の待機と要素検証を行います。
- **2段階認証(2FA)対応**: 2FAコード入力画面を検出し、ユーザーにコンソールからコード入力を促します。（TOTP自動生成の拡張も可能）
- **無限スクロール処理**: ツイート検索結果やリストメンバーページでコンテンツを動的に読み込むため、ページを繰り返しスクロールし、新しい要素がなくなるか上限回数に達するまでデータを収集します。
- **データ検証と保存**: 収集したデータをJSON形式で保存する前に、必須フィールドの存在やデータ形式を検証します。ファイル名にはタイムスタンプと収集対象の情報を含めます。
- **キャッシュ**: プロフィール情報など、一度収集したデータをローカルにキャッシュし、再実行時の重複アクセスを防ぎます。
- **デバッグ支援**: エラー発生時や特定ポイントで、ページのHTML、スクリーンショットを自動保存し、問題解決の手がかりを提供します。

---

### 3. セットアップ

#### 3.1 必要な環境
- Python 3.8以上
- pip (Pythonパッケージインストーラ)

#### 3.2 インストール手順
1.  **Playwrightのインストール**:
    ```bash
    pip install playwright
    ```
2.  **ブラウザドライバのインストール**:
    Playwrightが必要とするブラウザ（Chromium, Firefox, WebKit）をインストールします。通常はChromiumで十分です。
    ```bash
    playwright install chromium
    # または playwright install --with-deps chromium (依存関係もインストールする場合)
    ```

#### 3.3 認証情報の設定
Twitterのログイン情報は、以下のいずれかの方法で設定します。
1.  **環境変数（推奨）**:
    - `TWITTER_USERNAME`: あなたのTwitterユーザー名、メールアドレス、または電話番号
    - `TWITTER_PASSWORD`: あなたのTwitterパスワード
    ```bash
    export TWITTER_USERNAME="your_username"
    export TWITTER_PASSWORD="your_password"
    ```
    (Windowsの場合は `set` コマンドを使用)
2.  **キーリング (keyring)**:
    `keyring`ライブラリがインストールされていれば、安全に認証情報を保存・取得できます（初回設定が必要）。
    ```bash
    # pip install keyring (必要なら)
    # keyring set twitter username
    # keyring set twitter password
    ```
3.  **スクリプト実行時の入力**:
    上記の方法で認証情報が見つからない場合、スクリプトは実行時にコンソールでユーザー名とパスワードの入力を求めます。

**注意**: パスワードをコード内に直接記述することは避けてください。

#### 3.4 ファイル構造
このシステムは、以下のファイルとディレクトリ構造を想定しています。
```
vrc_cast_event_calender/
├── src/
│   ├── common/
│   │   ├── __init__.py
│   │   ├── adaptive_selectors.py  # 適応型セレクタークラス
│   │   └── web_structure_analyzer.py # デバッグ用ページ状態保存クラス
│   └── data_collection/
│       ├── __init__.py
│       ├── playwright_scraper.py    # ツイート収集メインスクリプト
│       └── list_collector.py        # リストメンバー収集メインスクリプト
├── data/
│   ├── raw_scraped_data/         # 収集したJSONデータ保存先
│   └── debug_data/               # HTML, スクリーンショット保存先
├── cache/                         # プロフィール等のキャッシュ保存先
└── twitter_scraper.log            # playwright_scraper のログファイル
└── twitter_list_collector.log     # list_collector のログファイル
```
`data/`, `cache/` ディレクトリは、スクリプト実行時に自動生成されます。

---

### 4. コア機能解説

#### 4.1 `playwright_scraper.py` (ツイート収集メイン)

##### `initialize_browser()`
- Playwrightを起動し、Chromiumブラウザインスタンスを作成します (`headless=False` で動作確認)。
- **検出回避**:
    - `args`: `--disable-blink-features=AutomationControlled` などの引数で自動化フラグを無効化。
    - `user_agent`: 一般的なブラウザのUser-Agent文字列を設定。
    - `locale`, `timezone_id`, `geolocation`: 日本語環境に偽装。
    - `add_init_script`: ページ読み込み前にJavaScriptを実行し、`navigator.webdriver` を `undefined` にしたり、`navigator.languages` を偽装します。
- ページ (`self.page`) とヘルパークラス (`WebStructureAnalyzer`, `AdaptiveSelectors`) を初期化します。

##### `login_to_twitter()`
- **認証情報取得**: 環境変数、キーリング、ユーザー入力の順で試行。
- **ページ遷移**: `page.goto("https://twitter.com/login", ...)` でログインページに移動。`wait_until="domcontentloaded"` で初期描画を待ちます。
- **要素待機**: 主要な入力フィールド (`input[name="text"]` など) が表示されるまで `page.wait_for_selector` で明示的に待機。読み込み失敗や構造変化に備えます。
- **ユーザー名入力**: `adaptive_selectors.find_input_by_any_attribute` を使用。
    - 候補リスト (`name=['text'], autocomplete=['username'], ...`) を定義。
    - `AdaptiveSelectors` がリスト内のセレクターを順に試し、最初に見つかった要素を返します。
- **「次へ」ボタン**: `adaptive_selectors.find_element_by_text_or_role` を使用。
    - テキスト (`['次へ', 'Next']`)、ロール (`'button'`)、`data-testid` (`['ocfEnterTextNextButton', 'next_link']`) を組み合わせて検索。
- **追加認証**: パスワード入力前に電話番号やユーザー名を再入力する画面が表示されることがあります。
    - まずパスワードフィールドを検索 (`name="password"`)。
    - 見つからない場合、追加認証用フィールド (`data-testid="ocfEnterTextTextInput"`) を検索し、ユーザー名を入力して再度「次へ」ボタンをクリックします。
- **パスワード入力**: `adaptive_selectors.find_input_by_any_attribute` でパスワードフィールド (`name="password"`) を検索し、入力。
- **「ログイン」ボタン**: `adaptive_selectors.find_element_by_text_or_role` で検索 (`['ログイン', 'Log in']`, `role='button'`, `data-testid=['ocfLoginButton', ...]`) してクリック。
- **`handle_2fa()`呼び出し**: ログインボタンクリック後、または追加認証後パスワードが見つからない場合に2FA処理を試みます。
- **ログイン成功確認**: ログイン後のタイムラインの主要コンテナ (`[data-testid="primaryColumn"]`) が表示されるか `page.wait_for_selector` で確認します。
- **エラーハンドリング**: 各ステップで `try...except PlaywrightTimeoutError` や `try...except Exception` を使用し、要素が見つからない場合や予期せぬエラーが発生した場合にログを出力し、`web_analyzer.capture_page_state` でデバッグ情報を保存します。

##### `handle_2fa()`
- 2FAコード入力フィールドを `adaptive_selectors.find_input_by_any_attribute` で検索 (`name=['challenge_response', 'text']`, `data-testid=['ocfEnterTextTextInput', ...]`)。
- フィールドが見つかった場合、コンソールでユーザーにコード入力を要求 (`input(...)`)。
- 入力されたコードをフィールドに `fill` し、「次へ」または「認証」ボタン (`find_element_by_text_or_role`) をクリック。

##### `scrape_tweets()`
- **URL生成**: 検索クエリをURLエンコードし、リアルタイム検索 (`f=live`) のURLを作成。
- **ページ遷移**: 検索結果ページに移動し、ネットワークが安定するまで待機 (`wait_until="networkidle"`)。
- **無限スクロール**:
    - `while` ループでページ最下部までスクロール (`page.evaluate('window.scrollTo(0, document.body.scrollHeight);')`)。
    - 新しいツイートが表示されるまで待機 (`page.wait_for_load_state('networkidle', ...)` または `asyncio.sleep`)。
    - ページの高さを比較し、変化がなくなったらスクロールを停止。
    - 新規ツイートが一定回数連続で見つからない場合も停止 (`consecutive_no_new_tweets`)。
    - 最大スクロール試行回数を設定 (`max_scroll_attempts`) し、無限ループを防止。
- **ツイート抽出**:
    - ツイート全体を囲む要素 (`article[data-testid="tweet"]`) を `page.locator(...).all()` で取得。
    - 各ツイート要素から情報を抽出:
        - **URL/ID**: ステータスリンク (`a[href*="/status/"]`) から抽出・整形。
        - **本文**: `[data-testid="tweetText"]` から取得。
        - **日時**: `time` 要素の `datetime` 属性から取得。
        - **ユーザー名/ハンドル**: `[data-testid="User-Name"]` 内のテキストから分離して取得。
    - 抽出した情報を辞書 (`tweet_data`) に格納し、リスト (`tweets_data`) に追加。
    - 取得済みツイートIDを `seen_tweet_ids` セットで管理し、重複を排除。
- **エラーハンドリング**: 個々のツイート抽出エラーは警告ログにとどめ、処理を継続。全体のスクレイピングエラーはログ出力とデバッグ情報保存。

##### `save_data()`
- 収集したデータ（ツイートリスト）とクエリ（プレフィックス用）を受け取る。
- ファイル名を生成 (`tweets_{safe_query}_{timestamp}.json`)。
- データをJSON形式で `data/raw_scraped_data/` に保存 (`json.dump`)。
- 簡単な検証: 保存後のファイルサイズが極端に小さくないか、JSONとして再読み込みできるかを確認。

##### `scrape()`, `main()`
- `initialize_browser`, `login_to_twitter`, `scrape_tweets`, `save_data`, `close_browser` を順に呼び出し、全体のスクレイピングフローを実行。
- `ConfigManager` から収集対象を取得し、ループ処理。

#### 4.2 `list_collector.py` (リストメンバー収集メイン)

##### `login_to_twitter()`, `handle_2fa()`
- `playwright_scraper.py` とほぼ同様のログイン・2FA処理。

##### `collect_list_members()`
- **URL**: 指定されたTwitterリストのURL。
- **ページ遷移**: リストページに移動。
- **無限スクロール**: ツイート検索と同様のロジックで、リストメンバーが表示されなくなるまでスクロール。
- **メンバー抽出**:
    - 各メンバーを表す要素 (`[data-testid="UserCell"]`) を取得。
    - セル内のリンク (`a[href*="/"][role="link"]`) からプロフィールURLを取得。
    - ハンドル名 (`div[dir="ltr"] > span:has-text("@")`) を取得し、重複チェック (`seen_handles` セット)。
    - 抽出したプロフィールURLをリスト (`member_urls`) に追加。
- **返り値**: 収集したプロフィールURLのリスト。

##### `scrape_profile_info()`
- **キャッシュ確認**: `SimpleCache.get(profile_url)` でキャッシュが存在すればそれを返す。
- **ページ遷移**: プロフィールURLに移動。
- **情報抽出**: Playwrightの `locator` を使用して各情報を取得。
    - **Bio**: `[data-testid="UserDescription"]`
    - **Name/Handle**: `[data-testid="UserName"]` 内の要素
    - **Location/Website/Join Date**: `[data-testid="UserProfileHeader_Items"]` 内の `span` 要素を走査し、テキスト内容や `aria-label` で判断。
    - **Follower/Following**: `a[href$="/followers"]`, `a[href$="/following"]` 内の `span span` から数値を取得。
    - **Pinned Tweet**: `[data-testid="UserPinnedTweet"] article [data-testid="tweetText"]` から本文を取得。
- **データ整形**: 取得した情報を辞書 (`profile_info`) に格納。
- **キャッシュ保存**: `SimpleCache.set(profile_url, profile_info)` で結果をキャッシュ。
- **返り値**: プロフィール情報の辞書。

##### `validate_and_save_data()`
- リストメンバーデータ用にカスタマイズされた検証。
- 必須フィールド (`profile_url`, `user_handle`, `bio`) の存在を確認。
- 有効なデータ項目が一つもない場合は保存を中止。
- ファイル名を生成 (`list_members_{list_id}_{timestamp}.json`)。
- JSON形式で保存、ファイルサイズ・再読み込み検証。

##### `collect()`, `main()`
- `initialize_browser`, `login_to_twitter`, `collect_list_members`, `scrape_profile_info`, `validate_and_save_data`, `close_browser` を順に呼び出し、リストメンバー収集フローを実行。

#### 4.3 `src/common/adaptive_selectors.py`

##### `AdaptiveSelectors` クラス
- 目的: CSSセレクターやXPathが変更されても、複数の代替手段で要素を見つけ出す。
- `__init__`: `page` (PlaywrightのPageオブジェクト) と `logger` を受け取る。

##### `find_input_by_any_attribute()`
- 複数の属性とその候補値 (`attributes={'name': ['text', 'username'], 'placeholder': [...], ...}`) を受け取る。
- 各属性と値の組み合わせで `input[attr='value']` セレクターを生成。
- `page.locator(selector)` で要素候補を取得。
- `locator.wait_for(state="visible", ...)` で要素が表示されるまで短時間待機。
- 最初に見つかった表示済みの要素 (`Locator`) を返す。タイムアウトした場合は `None`。

##### `find_element_by_text_or_role()`
- テキスト (`texts=['次へ', 'Next']` など)、ロール (`role='button'`)、`data-testid` (`data_testid=['ocfLoginButton']` など) を受け取る。
- Playwright推奨のロケーター生成メソッドを利用:
    - `page.get_by_role()`: ARIAロールで検索 (テキストも指定可能)。
    - `page.get_by_text()`: 表示テキストで検索。
    - `page.get_by_test_id()`: `data-testid` 属性で検索。
- 正規表現 (`re.compile(...)`) を使用してテキストの部分一致検索も可能 (`exact_text=False`)。
- 指定された条件で複数のロケーター生成関数 (`locator_funcs`) を作成。
- 各関数を実行し、得られた `Locator` に対して `locator.first.wait_for(state="visible", ...)` で待機。
- 最初に見つかった表示済みの要素 (`Locator`) を返す。

#### 4.4 `src/common/web_structure_analyzer.py`

##### `WebStructureAnalyzer` クラス
- 目的: スクレイピング中の特定時点でのページ状態を保存し、デバッグを容易にする。
- `__init__`: `page` と `logger` を受け取る。

##### `capture_page_state()`
- 状態名 (`state_name`) を受け取り、ファイル名の一部に使用。
- タイムスタンプ付きのベースファイル名を生成。
- **HTML保存**: `page.content()` でHTMLを取得し、`.html` ファイルに保存。
- **スクリーンショット保存**: `page.screenshot(path=..., full_page=True)` でページ全体のスクリーンショットを `.png` ファイルに保存。
- **JS状態取得 (注意点)**: `page.evaluate()` でJavaScriptを実行してページ内部の状態（URL、タイトルなど）を取得することも可能だが、複雑なJSコードや特定のページ状態では `SyntaxError` が発生することがある。ドキュメントのコードではこの部分はエラー回避のため一時的にコメントアウトされている。必要に応じて、単純なJS式を文字列として渡すなど、エラーが起きにくい形で実装する。

#### 4.5 `SimpleCache` クラス
- 目的: 頻繁にアクセスするが内容が変わりにくいデータ（例: プロフィール情報）をローカルに保存し、API負荷や実行時間を削減する。
- `__init__`: キャッシュディレクトリ (`cache/`) を指定・作成。
- `get(key)`: キー（通常はURLなど一意な識別子）に対応するJSONファイルを探し、存在すれば内容を読み込んで返す。
- `set(key, data)`: キーに対応するファイル名で、データをJSON形式で保存する。キーに含まれる特殊文字はファイル名として使えるように簡易的にサニタイズされる。

---

### 5. 実行方法

1.  **認証情報の設定**: 環境変数、キーリング、または実行時入力でTwitterの認証情報を設定します。
2.  **ツイート収集の実行**:
    ```bash
    python -m src.data_collection.playwright_scraper
    ```
    - `ConfigManager` 内の `scraping_targets` で `'query'` が指定されているものが対象となります。
    - 結果は `data/raw_scraped_data/tweets_{query}_{timestamp}.json` に保存されます。
3.  **リストメンバー収集の実行**:
    ```bash
    python -m src.data_collection.list_collector
    ```
    - `ConfigManager` 内の `scraping_targets` で `'list_url'` が指定されているものが対象となります。
    - 結果は `data/raw_scraped_data/list_members_{list_id}_{timestamp}.json` に保存されます。
    - 各メンバーのプロフィールは `cache/` ディレクトリにキャッシュされます。

#### `ConfigManager` クラス
- `playwright_scraper.py` と `list_collector.py` 内にあるこのクラスで、スクレイピング対象を指定します。
- `get('scraping_targets')` メソッドが返すリスト内の辞書で、`'query'` キーに検索文字列、`'list_url'` キーにリストのURLを指定します。両方記述することも可能です。

---

### 6. トラブルシューティング

#### ログインできない場合
- **認証情報**: 環境変数、キーリングの設定、入力した情報が正しいか再確認します。特にパスワードの特殊文字に注意。
- **セレクター**: Twitter(X)のUIが変更された可能性があります。
    - ブラウザの開発者ツール（F12キー）を開き、ログインページの要素（ユーザー名入力欄、パスワード入力欄、「次へ」/「ログイン」ボタン）を検証（Inspect）します。
    - `name`属性、`autocomplete`属性、`aria-label`、`data-testid`などを確認します。
    - `src/common/adaptive_selectors.py` 内の `find_input_by_any_attribute` や `find_element_by_text_or_role` の候補リストを確認・更新します。特に `input[name="text"]` や関連する `aria-label`、ボタンの `data-testid` が重要です。
- **待機時間**: ネットワーク遅延やページの読み込み速度により、要素が見つかる前にタイムアウトしている可能性があります。
    - `playwright_scraper.py`/`list_collector.py` 内の `asyncio.sleep()` や、`wait_for_selector`, `wait_for` の `timeout` 値を増やしてみてください（例: `timeout=30000` を `timeout=60000` に）。
- **デバッグ情報**: `data/debug_data/` ディレクトリに保存されたHTMLファイルやスクリーンショットを確認します。
    - `username_input_missing*.html` や `next_button_missing*.png` など、エラー発生時点のページ状態が記録されています。これにより、どの要素が見つからなかったのか、ページの表示がどうなっていたかを確認できます。
- **CAPTCHA / 追加認証**: ログイン試行が多すぎると、CAPTCHA認証や「予期しないログイン」などの追加認証が求められることがあります。スクリプトは現在CAPTCHAに自動対応していません。時間をおいて試すか、手動でブラウザからログインして認証を解除する必要があるかもしれません。

#### ツイート / メンバーが取得できない場合
- **ログイン状態**: ログインが成功しているかログで確認します。ログイン失敗時はスクレイピングできません。
- **スクロール**: 無限スクロールが途中で停止していないか確認します。
    - `scrape_tweets` や `collect_list_members` 内のスクロール停止条件（`max_scroll_attempts`, `consecutive_no_new_tweets/members`）が厳しすぎる可能性があります。値を調整してみてください。
    - ネットワークが不安定な場合、`wait_for_load_state('networkidle', ...)` が頻繁にタイムアウトするかもしれません。`asyncio.sleep()` による待機時間を延ばすことを検討します。
- **抽出セレクター**: ツイートやユーザーセル、プロフィール情報のHTML構造が変更された可能性があります。
    - 開発者ツールで実際の要素構造を確認し、`playwright_scraper.py` の `scrape_tweets` や `list_collector.py` の `collect_list_members`, `scrape_profile_info` 内の `locator()` や属性取得部分のセレクターを修正します (`[data-testid="tweet"]`, `[data-testid="UserCell"]`, `[data-testid="tweetText"]`, `[data-testid="UserDescription"]` など)。
- **リストの可視性**: 非公開リストや存在しないリストにアクセスしようとしていないか確認します。

#### Playwright関連エラー
- `playwright install chromium` を再度実行して、ブラウザドライバが正しくインストールされているか確認します。
- Playwrightライブラリとブラウザドライバのバージョン互換性に問題がないか確認します。
- `Exception ignored in: ` や `RuntimeError: Event loop is closed` などのエラーは、非同期処理の終了シーケンスやリソース解放の問題を示唆することがあります。`close_browser()` 内で `context`, `browser`, `playwright` が存在し、閉じられていないか確認してから `close()` や `stop()` を呼び出すように修正されていますが、環境によっては発生する可能性があります。

#### レートリミット / アカウント凍結リスク
- Twitterは自動化ツールによる過度なアクセスを制限しています。短時間に大量のリクエストを行うと、一時的なアクセス制限（レートリミット）や、最悪の場合アカウントが凍結されるリスクがあります。
- **対策**:
    - **適切な待機**: `asyncio.sleep()` を各リクエスト間やスクロール後に挿入し、アクセス間隔を空けます。
    - **User-Agent**: リアルなUser-Agentを使用します。
    - **ヘッドレスモード**: 開発・デバッグ中は `headless=False` で、実際の運用では `headless=True` も検討しますが、`False` の方が検出されにくい場合があります。
    - **アクセス頻度**: 一度に大量のデータを取得しようとせず、必要に応じて実行回数を分けたり、対象を絞り込みます。
    - **キャッシュ活用**: `SimpleCache` を活用し、不要な再アクセスを避けます。

---

### 7. カスタマイズ

- **収集対象の追加**:
    - ツイートの「いいね」数、リツイート数などを取得するには、`scrape_tweets` 内で対応する要素（例: `[data-testid="like"]`, `[data-testid="retweet"]`）を探し、そのテキストや `aria-label` から数値を抽出するロジックを追加します。
    - プロフィール情報に「ヘッダー画像URL」や「アカウント作成日」などを追加するには、`scrape_profile_info` 内で対応する要素を探し、`src` 属性やテキストを取得するコードを追加します。
- **データ保存形式**:
    - 現在はJSON形式ですが、`save_data` や `validate_and_save_data` を変更し、`pandas` ライブラリを使ってCSVファイルに保存したり、データベース（SQLite, PostgreSQLなど）に書き込むように拡張できます。
- **ヘッドレスモード**:
    - 安定動作が確認できたら、`initialize_browser` 内の `launch` オプションを `headless=True` に変更することで、ブラウザUIを表示せずにバックグラウンドで実行できます。ただし、検出リスクが若干上がる可能性があります。

---

### 8. 注意点

- **利用規約**: Twitter/Xの利用規約では、自動化ツールの使用やスクレイピングが制限または禁止されている場合があります。このスクリプトの使用は自己責任で行ってください。規約違反によるアカウント制限や凍結のリスクがあります。
- **API制限**: 短時間に大量のリクエストを行うと、TwitterのAPI制限に抵触し、一時的にアクセスできなくなる可能性があります。適切な待機時間を設けてください。
- **IPブロック**: 極端に頻繁なアクセスは、IPアドレスがブロックされる原因となることがあります。
- **UI変更**: Twitter/Xのウェブサイトは頻繁にデザインやHTML構造が変更されます。このドキュメントやコード内のセレクターは、将来的に動作しなくなる可能性があります。定期的なメンテナンスと、開発者ツールを使ったセレクターの確認・更新が必要です。`AdaptiveSelectors` は変更への耐性を高めますが、万能ではありません。

---

### 9. 付録

#### 9.1 参考情報
- **Playwright ドキュメント**: [https://playwright.dev/python/docs/intro](https://playwright.dev/python/docs/intro)
- **Playwright ロケーター**: [https://playwright.dev/python/docs/locators](https://playwright.dev/python/docs/locators)
- **ARIA Roles**: [https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles)

#### 9.2 主要セレクター一覧 (2025年4月時点の推定)

| 用途                     | セレクター例 (優先度順)                                                                 | 補足                                      |
| :----------------------- | :-------------------------------------------------------------------------------------- | :---------------------------------------- |
| **ログイン**             |                                                                                         |                                           |
| ユーザー名入力           | `input[name="text"]`, `input[autocomplete="username"]`, (古い:`input[name='session[username_or_email]']`) | `aria-label` も参照                   |
| パスワード入力           | `input[name="password"]`, `input[autocomplete="current-password"]`                        |                                           |
| 追加認証入力 (電話/User) | `input[data-testid="ocfEnterTextTextInput"]`, `input[name="text"]`                        | ログインフロー中間で表示される可能性あり  |
| 2FAコード入力            | `input[name="challenge_response"]`, `input[data-testid="LoginVerificationCodeForm-challengeInput"]` |                                           |
| 「次へ」ボタン           | Role:`button` + Text:`次へ`/`Next`, `[data-testid="ocfEnterTextNextButton"]`              |                                           |
| 「ログイン」ボタン         | Role:`button` + Text:`ログイン`/`Log in`, `[data-testid="ocfLoginButton"]`                  |                                           |
| **ツイート**             |                                                                                         |                                           |
| ツイート全体             | `article[data-testid="tweet"]`                                                          |                                           |
| 本文                     | `div[data-testid="tweetText"]`                                                          |                                           |
| 投稿日時                 | `time`                                                                                  | `datetime` 属性                         |
| ユーザー名/ハンドル      | `div[data-testid="User-Name"]` 内の `span`                                                | 分離ロジックが必要                        |
| ステータスリンク         | `a[href*="/status/"]`                                                                   | ID抽出用                                |
| **リストメンバー**       |                                                                                         |                                           |
| メンバーセル             | `div[data-testid="UserCell"]`                                                           |                                           |
| プロフィールリンク       | `div[data-testid="UserCell"] a[href*="/"][role="link"]`                                 |                                           |
| ハンドル名               | `div[data-testid="UserCell"] div[dir="ltr"] > span:has-text("@")`                       |                                           |
| **プロフィール**         |                                                                                         |                                           |
| Bio                      | `div[data-testid="UserDescription"]`                                                    |                                           |
| 名前                     | `div[data-testid="UserName"] div[dir="ltr"] span span`                                    |                                           |
| ハンドル名               | `div[data-testid="UserName"] div[dir="auto"] span:has-text("@")`                        |                                           |
| 場所/Web/参加日        | `div[data-testid="UserProfileHeader_Items"] span`                                       | テキストや `aria-label` で判別          |
| フォロー/フォロワー数    | `a[href$="/following"] span span`, `a[href$="/followers"] span span`                      | 数値の抽出が必要                          |
| ピン留めツイート本文     | `div[data-testid="UserPinnedTweet"] article [data-testid="tweetText"]`                  |                                           |

**重要**: 上記セレクターは執筆時点のものであり、将来変更される可能性があります。常に開発者ツールで最新の構造を確認してください。

Citations:
[1] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/d3a61455-58ef-494c-9a38-f3268b351f18/list_collector.py
[2] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/ba188d3f-0140-43f8-bb0f-defd30a7e0bc/playwright_scraper.py

---
Perplexity の Eliot より: pplx.ai/share