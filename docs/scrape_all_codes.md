提供されたPythonファイルを以下に示します。ファイルは役割ごとに分割されています。

## configuration\_manager.py

```python
import yaml
import importlib.util # importlib.util を使用

class ConfigurationManager:
    """
    設定ファイル (YAML) とデータスキーマ (Python) を読み込み、管理するクラス。
    """
    def __init__(self, main_config_file, scraping_targets_file="config/scraping_targets.yaml", data_schemas_file="models/data_schemas.py"):
        """
        ConfigurationManagerを初期化する。

        Args:
            main_config_file (str): メイン設定ファイルのパス。
            scraping_targets_file (str, optional): スクレイピングターゲット設定ファイルのパス。Defaults to "config/scraping_targets.yaml".
            data_schemas_file (str, optional): データスキーマ定義ファイルのパス。Defaults to "models/data_schemas.py".
        """
        self.main_config_file = main_config_file
        self.scraping_targets_file = scraping_targets_file
        self.data_schemas_file = data_schemas_file
        self.config = self._load_config() # 初期化時に設定を読み込む

    def _load_config(self):
        """
        設定ファイルとデータスキーマを読み込む内部メソッド。
        """
        config = {}
        try:
            # メイン設定ファイルの読み込み
            with open(self.main_config_file, 'r', encoding='utf-8') as f: # encodingを指定
                main_config = yaml.safe_load(f)
                if main_config: # ファイルが空でないことを確認
                    config.update(main_config)

            # スクレイピングターゲット設定ファイルの読み込み
            with open(self.scraping_targets_file, 'r', encoding='utf-8') as f:
                scraping_targets = yaml.safe_load(f)
                if scraping_targets: # ファイルが空でないことを確認
                    config['scraping_targets'] = scraping_targets
                else:
                    config['scraping_targets'] = [] # 空の場合は空リストをデフォルトとする

            # データスキーマの動的読み込み
            spec = importlib.util.spec_from_file_location("data_schemas", self.data_schemas_file)
            if spec and spec.loader: # specとloaderが存在するか確認
                data_schemas = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(data_schemas)
                # data_schemas.py に event_schema が定義されていることを期待
                if hasattr(data_schemas, 'event_schema'):
                    config['data_schemas'] = data_schemas.event_schema
                else:
                    # event_schema がない場合の警告やデフォルト処理
                    print(f"警告: {self.data_schemas_file} に 'event_schema' が定義されていません。")
                    config['data_schemas'] = None # または適切なデフォルトスキーマ
            else:
                 print(f"警告: データスキーマファイル {self.data_schemas_file} を読み込めませんでした。")
                 config['data_schemas'] = None

        except FileNotFoundError as e:
            print(f"エラー: 設定ファイルが見つかりません - {e}")
            # ここでエラーをraiseするか、デフォルト設定を返すかなどを検討
            # 例: raise e または config = self._get_default_config()
        except yaml.YAMLError as e:
            print(f"エラー: YAMLファイルの解析に失敗しました - {e}")
            # エラーハンドリング
        except Exception as e:
            print(f"エラー: 設定の読み込み中に予期せぬエラーが発生しました - {e}")
            # エラーハンドリング

        return config

    def get(self, key, default=None):
        """
        指定されたキーに対応する設定値を取得する。

        Args:
            key (str): 取得したい設定のキー。
            default (any, optional): キーが存在しない場合に返すデフォルト値。Defaults to None.

        Returns:
            any: 設定値またはデフォルト値。
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """
        指定されたキーに値を設定する（メモリ上）。
        永続化が必要な場合は save_config を別途呼び出す。

        Args:
            key (str): 設定するキー。
            value (any): 設定する値。
        """
        self.config[key] = value
        # 注意: このメソッドはファイルを自動保存しません。
        # self.save_config() # 必要であればここで保存処理を呼び出す

    def save_config(self):
        """
        現在の設定をメイン設定ファイルに保存する。
        注意: scraping_targets や data_schemas は通常別ファイル管理のため、
              ここではメイン設定ファイルのみを対象とするのが一般的。
              もし全設定を単一ファイルに保存したい場合はロジック修正が必要。
        """
        try:
            # main_config に含まれるべき項目のみを抽出して保存する方が安全
            # 例: main_config_data = {k: v for k, v in self.config.items() if k not in ['scraping_targets', 'data_schemas']}
            # 現在の実装では config 全体をダンプしているため注意
            with open(self.main_config_file, 'w', encoding='utf-8') as f: # encodingを指定
                yaml.dump(self.config, f, indent=4, allow_unicode=True) # allow_unicode=True で日本語も正しく出力
        except Exception as e:
            print(f"エラー: 設定の保存中にエラーが発生しました - {e}")

# 使用例 (もしこのファイルが直接実行された場合)
if __name__ == "__main__":
    # ダミーの設定ファイルを作成してテスト
    main_conf_path = "config/main_config_dummy.yaml"
    targets_path = "config/scraping_targets_dummy.yaml"
    schemas_path = "models/data_schemas_dummy.py"

    os.makedirs("config", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    with open(main_conf_path, "w", encoding='utf-8') as f:
        yaml.dump({"api_key": "YOUR_API_KEY", "timeout": 30}, f)
    with open(targets_path, "w", encoding='utf-8') as f:
        yaml.dump([{"query": "#TestQuery"}, {"list_url": "https://twitter.com/i/lists/12345"}], f)
    with open(schemas_path, "w", encoding='utf-8') as f:
        f.write("event_schema = {'title': str, 'date': str}\n")

    config_manager = ConfigurationManager(main_config_file=main_conf_path,
                                        scraping_targets_file=targets_path,
                                        data_schemas_file=schemas_path)

    print("読み込み成功:")
    print(f"API Key: {config_manager.get('api_key')}")
    print(f"Scraping Targets: {config_manager.get('scraping_targets')}")
    print(f"Data Schema: {config_manager.get('data_schemas')}")

    # 値を設定して保存（メインファイルにのみ反映される想定）
    config_manager.set("timeout", 60)
    config_manager.save_config()
    print("\n設定変更・保存後:")
    # 再度読み込んで確認 (別インスタンスで)
    config_manager_reloaded = ConfigurationManager(main_config_file=main_conf_path,
                                                 scraping_targets_file=targets_path,
                                                 data_schemas_file=schemas_path)
    print(f"Timeout: {config_manager_reloaded.get('timeout')}")

    # テスト用に作成したファイルを削除
    # os.remove(main_conf_path)
    # os.remove(targets_path)
    # os.remove(schemas_path)
    # os.rmdir("config")
    # os.rmdir("models")
```


## web\_structure\_analyzer.py

```python
import os
import logging
import json
from datetime import datetime
from playwright.async_api import Page, Error as PlaywrightError # PlaywrightErrorをインポート

class WebStructureAnalyzer:
    """
    PlaywrightのPageオブジェクトを受け取り、ウェブページの構造や状態を分析・記録するクラス。
    デバッグ用にHTML、スクリーンショット、その他の情報を保存する機能を持つ。
    """
    def __init__(self, page: Page, logger: logging.Logger, debug_data_dir: str = 'data/debug_data/'):
        """
        WebStructureAnalyzerを初期化する。

        Args:
            page (Page): 分析対象のPlaywright Pageオブジェクト。
            logger (logging.Logger): ログ出力用のロガーインスタンス。
            debug_data_dir (str, optional): デバッグデータ（HTML、スクリーンショット等）の保存先ディレクトリ。
                                             Defaults to 'data/debug_data/'.
        """
        self.page = page
        self.logger = logger
        self.debug_data_dir = debug_data_dir
        try:
            os.makedirs(self.debug_data_dir, exist_ok=True)
        except OSError as e:
            self.logger.error(f"デバッグディレクトリの作成に失敗しました: {self.debug_data_dir}, エラー: {e}")
            # ディレクトリが作成できない場合、機能が制限される可能性があることを警告
            self.logger.warning("デバッグデータの保存機能が利用できない可能性があります。")

    async def capture_page_state(self, state_name: str):
        """
        現在のページの状態（HTML、スクリーンショット）を指定された名前で記録する。

        Args:
            state_name (str): 記録する状態の名前（ファイル名の一部として使用）。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # ファイル名に使用できない文字を除去または置換
        safe_state_name = "".join(c for c in state_name if c.isalnum() or c in ('-', '_'))[:100] # 安全なファイル名生成
        base_filename = os.path.join(self.debug_data_dir, f"{safe_state_name}_{timestamp}")

        self.logger.info(f"ページ状態を記録中: {safe_state_name}")

        # ページが有効か確認
        if not self.page or self.page.is_closed():
            self.logger.warning(f"ページ状態の記録スキップ ({safe_state_name}): ページが閉じられているか無効です。")
            return

        try:
            # HTMLの保存
            html_filename = f"{base_filename}.html"
            try:
                html_content = await self.page.content()
                with open(html_filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info(f"HTMLを保存しました: {html_filename}")
            except PlaywrightError as e: # content() が失敗するケースに対応
                 self.logger.error(f"HTMLコンテンツの取得または保存に失敗しました: {e}")
            except Exception as e: # その他のファイル書き込みエラーなど
                 self.logger.error(f"HTMLの保存中に予期せぬエラーが発生しました: {e}", exc_info=True)


            # スクリーンショットの保存
            screenshot_filename = f"{base_filename}.png"
            try:
                await self.page.screenshot(path=screenshot_filename, full_page=True)
                self.logger.info(f"スクリーンショットを保存しました: {screenshot_filename}")
            except PlaywrightError as e: # screenshot() が失敗するケースに対応
                 self.logger.error(f"スクリーンショットの撮影または保存に失敗しました: {e}")
            except Exception as e: # その他のファイル書き込みエラーなど
                 self.logger.error(f"スクリーンショットの保存中に予期せぬエラーが発生しました: {e}", exc_info=True)


            # JSの状態（例: localStorage, sessionStorage）の取得 - 必要に応じて実装
            # self.logger.info("ページ状態(JS)の取得は現在実装されていません。")
            # try:
            #     local_storage = await self.page.evaluate("() => JSON.stringify(localStorage)")
            #     session_storage = await self.page.evaluate("() => JSON.stringify(sessionStorage)")
            #     js_state_filename = f"{base_filename}_js_state.json"
            #     with open(js_state_filename, 'w', encoding='utf-8') as f:
            #         json.dump({"localStorage": json.loads(local_storage), "sessionStorage": json.loads(session_storage)}, f, indent=4)
            #     self.logger.info(f"JS状態（ストレージ）を保存しました: {js_state_filename}")
            # except Exception as e:
            #     self.logger.error(f"JS状態の取得または保存中にエラー: {e}")

        except Exception as e:
            # ここに来ることは少ないはずだが、念のため包括的なエラーハンドリング
            self.logger.error(f"ページ状態の記録プロセス全体で予期せぬエラーが発生しました ({safe_state_name}): {e}", exc_info=True)

    async def analyze_web_structure(self):
        """
        現在のウェブページの基本的な構造情報を分析し、辞書として返す。
        （現在は基本的な情報取得とコンテンツ/スクショ保存のみ）

        Returns:
            dict: ページURL、タイトル、HTMLコンテンツ、スクリーンショットパスなどを含む辞書。
                  エラー発生時は {"error": "エラーメッセージ"} を返す。
        """
        try:
            # ページが有効か確認
            if not self.page or self.page.is_closed():
                self.logger.warning("構造分析スキップ: ページが閉じられています。")
                return {"error": "Page is closed"}

            # 基本情報の取得
            page_url = self.page.url
            page_title = await self.page.title()

            # コンテンツとスクリーンショットの保存（分析目的での保存）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            analysis_base = os.path.join(self.debug_data_dir, f"web_structure_analysis_{timestamp}")
            html_path = f"{analysis_base}.html"
            screenshot_path = f"{analysis_base}.png"

            html_content = ""
            try:
                html_content = await self.page.content()
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info(f"構造分析用HTMLを保存: {html_path}")
            except Exception as e:
                self.logger.error(f"構造分析用HTMLの取得・保存エラー: {e}")
                html_path = None # 保存失敗

            try:
                await self.page.screenshot(path=screenshot_path)
                self.logger.info(f"構造分析用スクリーンショットを保存: {screenshot_path}")
            except Exception as e:
                self.logger.error(f"構造分析用スクリーンショットの保存エラー: {e}")
                screenshot_path = None # 保存失敗

            # より詳細な分析（例：主要要素の特定、フォームの解析など）はここに追加可能
            # links = await self.page.locator('a').all_inner_texts()
            # headings = await self.page.locator('h1, h2, h3').all_inner_texts()

            structure_data = {
                "page_url": page_url,
                "page_title": page_title,
                "analysis_timestamp": timestamp,
                "html_saved_path": html_path,
                "screenshot_saved_path": screenshot_path,
                # "html_content": html_content, # 必要ならHTMLコンテンツ自体も含める（巨大になる可能性あり）
                # "extracted_links": links,
                # "extracted_headings": headings,
            }

            self.logger.info(f"ウェブページの構造分析が完了しました: {page_url}")
            return structure_data

        except PlaywrightError as e:
             self.logger.error(f"ウェブページの構造分析中にPlaywrightエラーが発生しました: {e}")
             return {"error": f"PlaywrightError: {e}"}
        except Exception as e:
            self.logger.error(f"ウェブページの構造分析中に予期せぬエラーが発生しました: {e}", exc_info=True)
            return {"error": f"UnexpectedError: {str(e)}"}

# 使用例 (もしこのファイルが直接実行された場合)
async def main():
    from playwright.async_api import async_playwright
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        analyzer = WebStructureAnalyzer(page, logger)

        try:
            await page.goto("https://example.com") # Example.comにアクセス
            await analyzer.capture_page_state("example_page_load") # 状態を記録
            structure_info = await analyzer.analyze_web_structure() # 構造を分析
            logger.info(f"分析結果: {structure_info}")

            # エラーケースのテスト（閉じたページ）
            await page.close()
            logger.info("ページを閉じて再度試行:")
            await analyzer.capture_page_state("example_page_closed")
            structure_info_closed = await analyzer.analyze_web_structure()
            logger.info(f"分析結果（閉じたページ）: {structure_info_closed}")

        except Exception as e:
            logger.error(f"メイン処理中にエラー: {e}")
        finally:
            if not browser.is_closed(): # ブラウザがまだ開いていれば閉じる
                 await browser.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```


## adaptive\_selectors.py

```python
import asyncio
import logging
import re
import time
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

class AdaptiveSelectors:
    """
    PlaywrightのPageオブジェクトを使用して、変化しやすいウェブページの要素を
    複数の属性、テキスト、ロールなどから柔軟に検索するためのヘルパークラス。
    """
    def __init__(self, page: Page, logger: logging.Logger):
        """
        AdaptiveSelectorsを初期化する。

        Args:
            page (Page): 操作対象のPlaywright Pageオブジェクト。
            logger (logging.Logger): ログ出力用のロガーインスタンス。
        """
        self.page = page
        self.logger = logger

    async def find_input_by_any_attribute(self, attributes: dict[str, list[str]], timeout=10000) -> Locator | None:
        """
        指定された複数の属性と値の組み合わせで input 要素を検索し、最初に見つかった
        可視状態の要素 (Locator) を返す。

        Args:
            attributes (dict[str, list[str]]): 検索対象の属性名をキー、属性値のリストを値とする辞書。
                                               例: {'name': ['username', 'email'], 'data-testid': ['login-input']}
            timeout (int, optional): 全ての属性値を試す合計のタイムアウト時間 (ミリ秒)。 Defaults to 10000.

        Returns:
            Locator | None: 最初に見つかった可視の input 要素の Locator。見つからない場合は None。
        """
        self.logger.info(f"属性による入力フィールド検索開始: {attributes}")
        start_time = time.time()

        # 試行回数を計算し、1試行あたりのタイムアウトを決定
        attempts = sum(len(values) for values in attributes.values() if isinstance(values, list))
        # 最小タイムアウト値を設定（短すぎると要素検出前にタイムアウトする可能性があるため）
        min_time_per_attempt = 500
        time_per_attempt = max(min_time_per_attempt, timeout // attempts if attempts > 0 else timeout)
        self.logger.debug(f"合計試行回数: {attempts}, 1試行あたり最大タイムアウト: {time_per_attempt:.0f}ms")

        for attr, values in attributes.items():
            if not isinstance(values, list):
                self.logger.warning(f"属性 '{attr}' の値がリストではありません。スキップします: {values}")
                continue
            for value in values:
                elapsed_time_ms = (time.time() - start_time) * 1000
                remaining_timeout_ms = timeout - elapsed_time_ms
                if remaining_timeout_ms  Locator | None:
        """
        指定されたテキスト、ロール、data-testid の組み合わせで要素を検索し、
        最初に見つかった可視状態の要素 (Locator) を返す。
        複数の条件で試行する。

        Args:
            texts (list[str] | str | None, optional): 検索対象のテキストまたはテキストのリスト。 Defaults to None.
            role (str | None, optional): 検索対象のARIAロール。 Defaults to None.
            data_testid (str | list[str] | None, optional): 検索対象の data-testid 属性値またはそのリスト。 Defaults to None.
            timeout (int, optional): 全ての条件を試す合計のタイムアウト時間 (ミリ秒)。 Defaults to 10000.
            exact_text (bool, optional): テキスト検索時に完全一致を要求するかどうか。 Defaults to False.

        Returns:
            Locator | None: 最初に見つかった可視の要素の Locator。見つからない場合は None。
        """
        # 入力引数の正規化
        if isinstance(texts, str):
            texts = [texts]
        if isinstance(data_testid, str):
            data_testid = [data_testid]

        start_time = time.time()
        self.logger.info(f"テキスト/ロール/TestID 検索開始: texts={texts}, role={role}, data_testid={data_testid}, exact={exact_text} (Timeout: {timeout}ms)")

        # 試行する Locator 生成関数のリストを作成
        locator_funcs = []
        locator_descriptions = [] # デバッグ用に各試行の説明を格納

        # Roleベースの検索
        if role:
            if texts:
                for text in texts:
                    # 完全一致
                    desc = f"Role='{role}', Text='{text}' (Exact: {exact_text})"
                    locator_funcs.append(lambda r=role, t=text: self.page.get_by_role(r, name=t, exact=exact_text))
                    locator_descriptions.append(desc)
                    # 部分一致（exact_text=False の場合のみ）
                    if not exact_text:
                        desc_re = f"Role='{role}', Text=REGEX('{re.escape(t)}') (Case-Insensitive)"
                        locator_funcs.append(lambda r=role, t=text: self.page.get_by_role(r, name=re.compile(re.escape(t), re.IGNORECASE)))
                        locator_descriptions.append(desc_re)
            else:
                 # Roleのみで検索
                 desc = f"Role='{role}'"
                 locator_funcs.append(lambda r=role: self.page.get_by_role(r))
                 locator_descriptions.append(desc)

        # Textベースの検索
        if texts:
            for text in texts:
                # 完全一致
                desc = f"Text='{text}' (Exact: {exact_text})"
                locator_funcs.append(lambda t=text: self.page.get_by_text(t, exact=exact_text))
                locator_descriptions.append(desc)
                # 部分一致（exact_text=False の場合のみ）
                if not exact_text:
                    desc_re = f"Text=REGEX('{re.escape(t)}') (Case-Insensitive)"
                    locator_funcs.append(lambda t=text: self.page.get_by_text(re.compile(re.escape(t), re.IGNORECASE)))
                    locator_descriptions.append(desc_re)

        # Data-testidベースの検索
        if data_testid:
            for tid in data_testid:
                desc = f"Data-testid='{tid}'"
                locator_funcs.append(lambda test_id=tid: self.page.get_by_test_id(test_id))
                locator_descriptions.append(desc)

        if not locator_funcs:
            self.logger.warning("検索条件が指定されていません (テキスト/ロール/TestID)")
            return None

        # 1試行あたりのタイムアウト計算
        attempts = len(locator_funcs)
        min_time_per_attempt = 1000 # 最低でも1秒は待つ
        time_per_attempt = max(min_time_per_attempt, timeout // attempts if attempts > 0 else timeout)
        self.logger.debug(f"合計試行回数: {attempts}, 1試行あたり最大タイムアウト: {time_per_attempt:.0f}ms")


        for i, locator_func in enumerate(locator_funcs):
            elapsed_time_ms = (time.time() - start_time) * 1000
            remaining_timeout_ms = timeout - elapsed_time_ms
            if remaining_timeout_ms  0:
                    self.logger.info(f"要素発見 ({description}) - {count}件。最初の要素を返します。")
                    return locator.first # 最初の要素のLocatorを返す
                else:
                    # wait_forが成功しても直後に要素が消える稀なケースへの対応
                    self.logger.warning(f"要素 ({description}) は可視待機後、見つかりませんでした (0件)。")

            except PlaywrightTimeoutError:
                self.logger.warning(f"要素試行 {i+1} ({description}) はタイムアウトしました。")
            except PlaywrightError as pe: # ページが閉じた場合など
                 if "closed" in str(pe).lower():
                     self.logger.error(f"要素検索中にページ/コンテキストが閉じられました ({description}): {pe}")
                     return None
                 else:
                     self.logger.error(f"要素試行 {i+1} ({description}) 中にPlaywrightエラー: {pe}", exc_info=False)
            except Exception as e: # その他の予期せぬエラー
                self.logger.error(f"要素試行 {i+1} ({description}) 中に予期せぬエラー: {e}", exc_info=True)

        self.logger.error("指定されたどの条件でも要素が見つかりませんでした。")
        return None

# 使用例 (もしこのファイルが直接実行された場合)
async def main():
    from playwright.async_api import async_playwright
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("AdaptiveSelectorsTest")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Headless=Falseで動作確認
        page = await browser.new_page()
        adapter = AdaptiveSelectors(page, logger)

        try:
            # テスト用HTMLコンテンツを設定
            await page.set_content("""
                
                    テストページ
                    
                    
                    ログイン
                    キャンセル 
                    操作完了
                    詳細はこちら
                
            """)

            # --- find_input_by_any_attribute のテスト ---
            logger.info("\n--- find_input_by_any_attribute テスト ---")
            # 存在する属性で検索
            username_input = await adapter.find_input_by_any_attribute(
                {'name': ['user', 'username'], 'placeholder': ['ユーザー名']}, timeout=5000)
            if username_input:
                await username_input.fill("test_user")
                logger.info("ユーザー名入力フィールドに書き込み成功")
            else:
                logger.error("ユーザー名入力フィールドが見つかりません")

            # 存在しない属性で検索
            logger.info("\n存在しない属性で検索:")
            non_existent_input = await adapter.find_input_by_any_attribute(
                {'id': ['non-existent']}, timeout=2000)
            if not non_existent_input:
                logger.info("存在しない入力フィールドは期待通り見つかりませんでした")

            # data-testidで検索
            password_input = await adapter.find_input_by_any_attribute(
                {'data-testid': ['pwd-input']}, timeout=3000)
            if password_input:
                 await password_input.fill("password123")
                 logger.info("パスワード入力フィールドに書き込み成功")
            else:
                 logger.error("パスワード入力フィールドが見つかりません")


            # --- find_element_by_text_or_role のテスト ---
            logger.info("\n--- find_element_by_text_or_role テスト ---")
            # ロールとテキストで検索 (完全一致)
            login_button = await adapter.find_element_by_text_or_role(
                texts='ログイン', role='button', timeout=3000, exact_text=True)
            if login_button:
                logger.info(f"ログインボタン発見 (Role & Exact Text): {await login_button.text_content()}")
            else:
                logger.error("ログインボタン (Role & Exact Text) が見つかりません")

            # テキストのみで検索 (部分一致)
            details_link = await adapter.find_element_by_text_or_role(
                texts='詳細', timeout=3000, exact_text=False)
            if details_link:
                 logger.info(f"詳細リンク発見 (Partial Text): {await details_link.text_content()}")
            else:
                 logger.error("詳細リンク (Partial Text) が見つかりません")

            # data-testidで検索
            message_box = await adapter.find_element_by_text_or_role(
                data_testid='message-box', timeout=3000)
            if message_box:
                 logger.info(f"メッセージボックス発見 (TestID): {await message_box.text_content()}")
            else:
                 logger.error("メッセージボックス (TestID) が見つかりません")

            # 存在しない要素を検索
            logger.info("\n存在しない要素を検索:")
            non_existent_element = await adapter.find_element_by_text_or_role(
                texts='存在しないテキスト', role='alert', timeout=2000)
            if not non_existent_element:
                logger.info("存在しない要素は期待通り見つかりませんでした")


            await asyncio.sleep(2) # 結果を視認するための待機

        except Exception as e:
            logger.error(f"テスト中にエラーが発生: {e}", exc_info=True)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```


## playwright\_scraper.py

```python
import asyncio
import json
import os
import time
import logging
import re
from datetime import datetime
from urllib.parse import quote # URLエンコード用

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    Page, # 型ヒント用
    BrowserContext # 型ヒント用
)

# --- 依存関係 ---
# プロジェクト構成に合わせて実際のモジュールをインポートする
# from src.common.web_structure_analyzer import WebStructureAnalyzer
# from src.common.adaptive_selectors import AdaptiveSelectors
# from src.common.configuration_manager import ConfigurationManager # 設定管理クラス
# from src.common.simple_cache import SimpleCache # キャッシュクラス

# --- ↓↓↓ 仮の依存クラス (実際のプロジェクトでは削除または置き換え) ↓↓↓ ---
class WebStructureAnalyzer:
    """仮のWebStructureAnalyzerクラス"""
    def __init__(self, page, logger): self.page = page; self.logger = logger
    async def capture_page_state(self, state_name): self.logger.info(f"仮: ページ状態キャプチャ ({state_name})")
    async def analyze_web_structure(self): self.logger.info("仮: 構造分析実行"); return {}

class AdaptiveSelectors:
    """仮のAdaptiveSelectorsクラス"""
    def __init__(self, page, logger): self.page = page; self.logger = logger
    async def find_input_by_any_attribute(self, attributes: dict, timeout=10000):
        self.logger.info(f"仮: find_input_by_any_attribute ({attributes})")
        # 実際の find_input_by_any_attribute のロジックを模倣 (簡易版)
        for attr, values in attributes.items():
            for value in values:
                selector = f"input[{attr}='{value}']"
                try:
                    element = self.page.locator(selector).first
                    # 簡易的な可視性チェック (実際は wait_for を使うべき)
                    is_visible = await element.is_visible(timeout=max(500, timeout // (sum(len(v) for v in attributes.values()) or 1)))
                    if is_visible:
                        self.logger.info(f"仮: 要素発見 ({selector})")
                        return element
                except PlaywrightTimeoutError: pass # タイムアウトは無視して次へ
                except Exception as e: self.logger.warning(f"仮: セレクタ検索エラー ({selector}): {e}")
        self.logger.error("仮: 入力要素見つからず")
        return None

    async def find_element_by_text_or_role(self, texts=None, role=None, data_testid=None, timeout=10000, exact_text=False):
        self.logger.info(f"仮: find_element_by_text_or_role (texts={texts}, role={role}, testid={data_testid})")
        # 実際の find_element_by_text_or_role のロジックを模倣 (簡易版)
        locators_to_try = []
        # ここで locator を組み立てるロジック (get_by_role, get_by_text, get_by_test_id)
        # ... (省略) ...
        # ダミーで最初の要素を試す
        try:
            if role and texts:
                 locator = self.page.get_by_role(role, name=texts[0] if isinstance(texts, list) else texts, exact=exact_text)
                 locators_to_try.append(locator)
            elif texts:
                 locator = self.page.get_by_text(texts[0] if isinstance(texts, list) else texts, exact=exact_text)
                 locators_to_try.append(locator)
            elif data_testid:
                 locator = self.page.get_by_test_id(data_testid[0] if isinstance(data_testid, list) else data_testid)
                 locators_to_try.append(locator)
            elif role:
                 locator = self.page.get_by_role(role)
                 locators_to_try.append(locator)

            if not locators_to_try: return None # 試行対象がなければNone

            # 最初の候補だけ試す簡易ロジック
            locator = locators_to_try[0].first
            is_visible = await locator.is_visible(timeout=timeout)
            if is_visible:
                self.logger.info(f"仮: 要素発見 (最初の候補)")
                return locator
        except PlaywrightTimeoutError: self.logger.warning("仮: 要素試行タイムアウト")
        except Exception as e: self.logger.warning(f"仮: 要素試行エラー: {e}")
        self.logger.error("仮: 要素見つからず")
        return None

class SimpleCache:
    """仮のSimpleCacheクラス"""
    def __init__(self, cache_dir='cache', logger=None):
        self.cache_dir = cache_dir
        self.logger = logger or logging.getLogger(__name__)
        os.makedirs(cache_dir, exist_ok=True)
    def get(self, key): self.logger.info(f"仮: キャッシュ取得 ({key})"); return None # キャッシュは常にミス
    def set(self, key, data): self.logger.info(f"仮: キャッシュ設定 ({key})")

class ConfigManager:
    """仮のConfigManagerクラス"""
    def get(self, key, default=None):
        if key == 'scraping_targets':
            # scraping_targets.yaml から読み込む想定のデータ例
            return [
                # {'query': '#VRChat event'},
                 {'query': 'lang:ja (イベント OR 開催 OR 主催 OR join OR ジョイン OR リクイン OR reqin OR リクエストインバイト OR "request invite" OR 本日 OR 営業 OR 応募) (VRChat OR VRC) min_retweets:3'},
                 {'list_url': 'https://x.com/i/lists/1834685283276935624'} # リスト収集ターゲット例
            ]
        elif key == 'twitter_credentials': # 認証情報用のキー（例）
             return {'username': os.environ.get("TWITTER_USERNAME"), 'password': os.environ.get("TWITTER_PASSWORD")}
        return default # 他のキーはデフォルト値を返す
# --- ↑↑↑ 仮の依存クラスここまで ↑↑↑ ---


class EnhancedTwitterScraper:
    """
    Playwrightを使用してTwitter (X) から情報をスクレイピングするクラス。
    ログイン、ツイート検索、データ保存などの機能を持つ。
    """
    def __init__(self, config_manager: ConfigManager, logger: logging.Logger | None = None):
        """
        EnhancedTwitterScraperを初期化する。

        Args:
            config_manager (ConfigManager): 設定管理オブジェクト。
            logger (logging.Logger | None, optional): ログ出力用のロガー。 Defaults to None (新規作成).
        """
        self.config_manager = config_manager

        # ロガー設定
        if logger is None:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler("twitter_scraper.log", encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger

        # 設定値の取得
        self.scraping_targets = self.config_manager.get('scraping_targets', []) # デフォルトは空リスト
        # self.credentials = self.config_manager.get('twitter_credentials', {}) # 認証情報をConfigManagerから取得する場合

        # ディレクトリ設定と作成
        self.raw_data_dir = self.config_manager.get('raw_data_dir', 'data/raw_scraped_data/')
        self.debug_data_dir = self.config_manager.get('debug_data_dir', 'data/debug_data/')
        for directory in [self.raw_data_dir, self.debug_data_dir]:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                 self.logger.error(f"ディレクトリ作成失敗: {directory}, エラー: {e}")

        # 依存オブジェクトの初期化
        self.cache = SimpleCache(cache_dir=self.config_manager.get('cache_dir', 'cache'), logger=self.logger)

        # Playwright関連オブジェクトの初期化 (None)
        self.playwright: async_playwright | None = None
        self.browser: Browser | None = None # playwright.async_api.Browser 型ヒント追加
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        # 依存クラスのインスタンス化 (ページが必要なものはブラウザ初期化後)
        self.web_analyzer: WebStructureAnalyzer | None = None
        self.adaptive_selectors: AdaptiveSelectors | None = None

    async def initialize_browser(self, headless: bool = False, proxy_settings: dict | None = None) -> bool:
        """
        Playwrightブラウザを初期化し、ページオブジェクトを作成する。
        ステルスオプションやプロキシ設定も考慮。

        Args:
            headless (bool, optional): ヘッドレスモードで起動するかどうか。Defaults to False.
            proxy_settings (dict | None, optional): プロキシ設定 (例: {'server': 'http://proxy.com:port', 'username': 'user', 'password': 'pwd'})。 Defaults to None.

        Returns:
            bool: 初期化が成功したかどうか。
        """
        try:
            self.logger.info(f"Playwright ブラウザ初期化開始 (Headless: {headless})")
            self.playwright = await async_playwright().start()

            # playwright-stealth を使う場合 (オプション)
            # try:
            #     from playwright_stealth import stealth_async
            #     self.logger.info("playwright-stealth をロードしました。")
            # except ImportError:
            #     self.logger.info("playwright-stealth はインストールされていません。")
            #     stealth_async = None # 利用不可

            browser_launch_options = {
                'headless': headless,
                'args': [
                    '--disable-blink-features=AutomationControlled', # 自動化検出回避
                    '--start-maximized',
                    '--no-sandbox', # Linux環境での安定性向上 (Docker等)
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-plugins-discovery',
                    '--disable-infobars', # "Chrome is being controlled by automated test software" バーを非表示
                    # '--window-size=1920,1080', # 必要に応じて指定
                    # '--disable-gpu', # GPU関連の問題がある場合に試す
                ]
            }
            # プロキシ設定を追加
            if proxy_settings:
                browser_launch_options['proxy'] = proxy_settings
                self.logger.info(f"プロキシ設定を使用: {proxy_settings.get('server')}")


            self.browser = await self.playwright.chromium.launch(**browser_launch_options)
            self.logger.info("Chromium ブラウザを起動しました。")

            context_options = {
                'user_agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36", # 一般的なUA
                'viewport': {"width": 1920, "height": 1080},
                'locale': "ja-JP",
                'timezone_id': "Asia/Tokyo",
                'geolocation': {"latitude": 35.6895, "longitude": 139.6917}, # 東京 (任意)
                'permissions': ["geolocation"], # 位置情報許可
                'color_scheme': "no-preference", # OS設定依存
                'device_scale_factor': 1.0,
                # 'java_script_enabled': True, # デフォルトで有効
                # 'accept_downloads': True, # ダウンロードを許可する場合
            }

            self.context = await self.browser.new_context(**context_options)
            self.logger.info("ブラウザコンテキストを作成しました。")

            # ステルス化 (playwright-stealth がある場合)
            # if stealth_async:
            #     try:
            #         await stealth_async(self.context)
            #         self.logger.info("playwright-stealth を適用しました。")
            #     except Exception as stealth_err:
            #         self.logger.error(f"playwright-stealth の適用中にエラー: {stealth_err}")


            # WebDriver フラグやその他の検出ポイントを隠蔽する init スクリプト
            await self.context.add_init_script("""
                // WebDriver フラグを隠蔽
                if (navigator.webdriver) {
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                }
                // Chrome オブジェクトの偽装 (一部サイトでの検出回避)
                if (window.navigator.chrome) {
                     window.navigator.chrome = { runtime: {} }; // 簡易的な偽装
                }
                if (window.chrome) {
                     window.chrome = { app: { isInstalled: false }, runtime: {} }; // 簡易的な偽装
                }
                // Permissions API の偽装 (通知許可など)
                if (Notification && Notification.permission) {
                    const originalPermission = Notification.permission;
                    Object.defineProperty(Notification, 'permission', {
                        get: () => originalPermission === 'denied' ? 'denied' : 'default', // denied 以外は default に見せる
                        configurable: true
                    });
                }
                // navigator.languages の偽装 (一貫性を持たせる)
                try {
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ja-JP', 'ja', 'en-US', 'en'], // ブラウザ設定と合わせる
                        configurable: true
                    });
                } catch (e) { console.warn('Failed to modify navigator.languages:', e); }
                // プラグイン情報の偽装 (より高度な検出対策)
                // try {
                //     Object.defineProperty(navigator, 'plugins', {
                //         get: () => [ {name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format'} ], // ダミープラグイン
                //         configurable: true
                //     });
                // } catch (e) { console.warn('Failed to modify navigator.plugins:', e); }
                // WebGL ベンダー情報の偽装 (より高度な検出対策)
                // try {
                // const getParameter = WebGLRenderingContext.prototype.getParameter;
                // WebGLRenderingContext.prototype.getParameter = function(parameter) {
                //   if (parameter === 37445) { return 'Intel Open Source Technology Center'; } // VENDOR
                //   if (parameter === 37446) { return 'Mesa DRI Intel(R) Ivybridge Mobile '; } // RENDERER
                //   return getParameter(parameter);
                // };
                // } catch(e) { console.warn('Failed to modify WebGL parameters:', e); }
            """)
            self.logger.info("検出対策用の init スクリプトを追加しました。")

            self.page = await self.context.new_page()
            self.logger.info("新しいページを作成しました。")

            # 依存クラスのインスタンス化 (ページオブジェクトが必要なもの)
            self.web_analyzer = WebStructureAnalyzer(self.page, self.logger, self.debug_data_dir)
            self.adaptive_selectors = AdaptiveSelectors(self.page, self.logger)

            self.logger.info("ブラウザとページの初期化が完了しました。")
            return True

        except PlaywrightError as pe:
            self.logger.error(f"Playwright関連のエラーによりブラウザ初期化失敗: {pe}", exc_info=True)
            await self.close_browser() # 失敗した場合でも可能な限りクリーンアップ
            return False
        except Exception as e:
            self.logger.error(f"予期せぬエラーによりブラウザ初期化失敗: {e}", exc_info=True)
            await self.close_browser() # 失敗した場合でも可能な限りクリーンアップ
            return False

    async def close_browser(self):
        """
        Playwright関連のリソース（ページ、コンテキスト、ブラウザ）を安全に閉じる。
        """
        self.logger.info("ブラウザ関連リソースのクローズ処理を開始します。")

        # ページを閉じる
        if hasattr(self, 'page') and self.page and not self.page.is_closed():
            try:
                await self.page.close()
                self.logger.info("ページを閉じました。")
            except PlaywrightError as e:
                self.logger.error(f"ページのクローズ中にエラー: {e}")
            except Exception as e:
                self.logger.error(f"ページのクローズ中に予期せぬエラー: {e}")
        self.page = None # 参照をクリア

        # コンテキストを閉じる
        # context.is_closed() は時々問題を起こすため、存在チェックのみにする
        if hasattr(self, 'context') and self.context:
            try:
                await self.context.close()
                self.logger.info("コンテキストを閉じました。")
            except PlaywrightError as e:
                # 既に閉じられている場合のエラーは無視、それ以外はログ記録
                if "context closed" not in str(e).lower():
                    self.logger.error(f"コンテキストのクローズ中にエラー: {e}")
                else:
                    self.logger.debug(f"コンテキストは既に閉じられていたか、クローズ中に軽微なエラー: {e}")
            except Exception as e:
                 self.logger.error(f"コンテキストのクローズ中に予期せぬエラー: {e}")
        self.context = None # 参照をクリア

        # ブラウザを閉じる
        if hasattr(self, 'browser') and self.browser and self.browser.is_connected():
            try:
                await self.browser.close()
                self.logger.info("ブラウザを閉じました。")
            except PlaywrightError as e:
                self.logger.error(f"ブラウザのクローズ中にエラー: {e}")
            except Exception as e:
                 self.logger.error(f"ブラウザのクローズ中に予期せぬエラー: {e}")
        self.browser = None # 参照をクリア

        # Playwrightプロセスを停止
        if hasattr(self, 'playwright') and self.playwright:
            try:
                await self.playwright.stop()
                self.logger.info("Playwrightプロセスを停止しました。")
            except Exception as e:
                self.logger.error(f"Playwrightプロセスの停止中にエラー: {e}")
        self.playwright = None # 参照をクリア

        self.logger.info("ブラウザ関連リソースのクローズ処理が完了しました。")

    async def _check_page_closed(self, operation_name: str) -> bool:
        """処理実行前にページが閉じられていないか確認し、ログを出力するヘルパー"""
        if not self.page or self.page.is_closed():
            self.logger.error(f"{operation_name} を実行できません: ページが閉じられています。")
            return True
        return False

    async def login_to_twitter(self) -> bool:
        """
        Twitter (X) にログインする。
        認証情報は環境変数 (TWITTER_USERNAME, TWITTER_PASSWORD)、keyring、
        またはユーザー入力から取得する。

        Returns:
            bool: ログインが成功したかどうか。
        """
        if await self._check_page_closed("Twitterログイン"): return False
        assert self.page is not None # 型チェック用 (check_page_closedで確認済み)
        assert self.adaptive_selectors is not None # 初期化されているはず
        assert self.web_analyzer is not None # 初期化されているはず

        self.logger.info("Twitter ログインプロセス開始")

        # --- 認証情報取得 ---
        username = os.environ.get("TWITTER_USERNAME")
        password = os.environ.get("TWITTER_PASSWORD")

        # 環境変数がない場合、keyring を試す
        if not username or not password:
            self.logger.info("環境変数に認証情報が見つからないため、keyring を試します。")
            try:
                import keyring
                username = keyring.get_password("twitter", "username")
                password = keyring.get_password("twitter", "password")
                if username and password:
                    self.logger.info("keyring から認証情報を取得しました。")
                else:
                    self.logger.info("keyring に認証情報が見つかりませんでした。")
            except ImportError:
                self.logger.info("keyring がインストールされていません。ユーザー入力を試みます。")
            except Exception as e:
                self.logger.warning(f"keyring からの認証情報読み込み中にエラー: {e}")

        # keyringでも取得できない場合、ユーザー入力を求める (インタラクティブ環境のみ)
        if not username or not password:
            self.logger.info("認証情報が見つからないため、ユーザー入力を求めます。")
            # CI環境などでは input() が機能しないため、EOFError をハンドル
            try:
                # isatty() でインタラクティブな環境か簡易的に判定
                if os.isatty(0): # 標準入力がターミナルに接続されているか
                    print("--------------------------------------------------")
                    print("Twitter (X) の認証情報が必要です。")
                    username = input("ユーザー名またはメールアドレス: ")
                    # getpass を使う方が望ましいが、依存を増やさないため input を使用
                    # import getpass
                    # password = getpass.getpass("パスワード: ")
                    password = input("パスワード: ")
                    print("--------------------------------------------------")
                else:
                    self.logger.warning("非インタラクティブ環境のため、ユーザー入力はスキップされました。")
                    return False # 認証情報がないと進めない
            except EOFError:
                self.logger.error("ユーザー入力の取得中にEOFErrorが発生しました。非インタラクティブ環境では実行できません。")
                return False
            except Exception as e:
                 self.logger.error(f"ユーザー入力の取得中に予期せぬエラー: {e}")
                 return False

        # 最終チェック
        if not username or not password:
            self.logger.error("Twitter のユーザー名またはパスワードが取得できませんでした。")
            return False

        # パスワードはログに出力しない
        self.logger.info(f"使用するユーザー名: {username}")
        self.logger.info(f"使用するパスワード: {'*' * len(password)}")

        # --- ログインプロセス ---
        try:
            login_url = "https://twitter.com/login" # または "https://x.com/login"
            self.logger.info(f"ログインページに移動します: {login_url}")
            if await self._check_page_closed("ログインページへの移動"): return False
            await self.page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            self.logger.info("ページ遷移完了、要素待機開始")

            # ユーザー名入力フィールドが表示されるまで待機
            try:
                if await self._check_page_closed("ユーザー名フィールド待機"): return False
                # より多くのセレクタ候補を指定
                await self.page.wait_for_selector(
                    'input[name="text"], input[autocomplete="username"], input[aria-label*="ユーザー名"], input[aria-label*="username"]',
                    timeout=30000
                )
                self.logger.info("ログインページの主要入力フィールドを検出")
            except PlaywrightTimeoutError as e:
                self.logger.error(f"ログインページの主要入力フィールド待機中にタイムアウト: {e}")
                await self.web_analyzer.capture_page_state("login_page_load_fail_or_changed")
                return False

            # --- ユーザー名入力 ---
            self.logger.info("ユーザー名入力フィールドを検索・入力します")
            if await self._check_page_closed("ユーザー名入力"): return False
            username_input = await self.adaptive_selectors.find_input_by_any_attribute(
                {
                    'name': ['text'],
                    'autocomplete': ['username'],
                    'aria-label': [
                        '電話番号、メールアドレス、またはユーザー名', 'Phone, email address, or username',
                        '電話番号またはメールアドレス', 'Phone or email address',
                        'ユーザー名', 'Username'
                    ],
                    'type': ['text', 'email']
                },
                timeout=15000
            )
            if not username_input:
                self.logger.error("ユーザー名入力フィールドが見つかりませんでした。")
                await self.web_analyzer.capture_page_state("username_input_missing")
                return False
            await username_input.fill(username)
            await asyncio.sleep(0.5 + random.uniform(0.1, 0.4)) # 短いランダム待機

            # --- 「次へ」ボタン ---
            self.logger.info("「次へ」ボタンを検索・クリックします")
            if await self._check_page_closed("「次へ」ボタン検索"): return False
            next_button = await self.adaptive_selectors.find_element_by_text_or_role(
                texts=['次へ', 'Next'],
                role='button',
                data_testid=['ocfEnterTextNextButton', 'next_link', 'allow'], # 'allow' は電話番号連携などで表示される場合がある
                timeout=10000
            )
            if not next_button:
                self.logger.error("「次へ」ボタンが見つかりませんでした。")
                await self.web_analyzer.capture_page_state("next_button_missing")
                return False
            await next_button.click()
            self.logger.info("「次へ」ボタンをクリックしました。")
            await asyncio.sleep(1.5 + random.uniform(0.2, 0.8)) # 遷移のためのランダム待機

            # --- パスワード入力 / 追加認証ハンドリング ---
            # パスワード入力と追加認証（ユーザー名/電話番号再入力）の両方の可能性に対応
            password_input = None
            additional_input_handled = False # 追加認証入力フィールドを処理したかどうかのフラグ

            # まずはパスワードフィールドを試す
            try:
                if await self._check_page_closed("パスワード/追加認証フィールド検索"): return False
                self.logger.info("パスワード入力フィールドを検索します。")
                password_input = await self.adaptive_selectors.find_input_by_any_attribute(
                    {
                        'name': ['password'],
                        'type': ['password'],
                        'autocomplete': ['current-password']
                    },
                    timeout=10000 # パスワードフィールドは比較的すぐ表示されるはず
                )
                if password_input:
                     self.logger.info("パスワード入力フィールドを検出しました。")

            except PlaywrightTimeoutError:
                self.logger.info("パスワード入力フィールドが見つかりません。追加認証の可能性をチェックします。")

            # パスワードフィールドが見つからない場合、追加認証フィールドを試す
            if not password_input:
                if await self._check_page_closed("追加認証フィールド検索"): return False
                self.logger.info("追加認証フィールド（電話番号/ユーザー名）を検索します。")
                additional_input = await self.adaptive_selectors.find_input_by_any_attribute(
                    {
                        'data-testid': ['ocfEnterTextTextInput', 'challenge_response'],
                        'name': ['text', 'challenge_response'], # name属性も考慮
                        'aria-label': [
                            '電話番号またはユーザー名', 'Phone number or username',
                            'ユーザー名', 'Username',
                            'Enter your phone number or username' # 英語パターン追加
                        ]
                    },
                    timeout=7000 # 追加認証は少し待つ
                )
                if additional_input:
                    self.logger.warning("追加認証（電話番号/ユーザー名）が求められました。ユーザー名を入力します。")
                    if await self._check_page_closed("追加認証入力"): return False
                    await additional_input.fill(username) # ここではユーザー名を入れることが多い
                    additional_input_handled = True # フラグを立てる
                    await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))

                    # 追加認証画面の「次へ」ボタンをクリック
                    self.logger.info("追加認証画面の「次へ」ボタンを検索・クリックします。")
                    if await self._check_page_closed("追加認証「次へ」ボタン検索"): return False
                    next_button_again = await self.adaptive_selectors.find_element_by_text_or_role(
                        texts=['次へ', 'Next'],
                        role='button',
                        data_testid=['ocfEnterTextNextButton'], # テストIDも考慮
                        timeout=10000
                    )
                    if not next_button_again:
                        self.logger.error("追加認証画面の「次へ」ボタンが見つかりません。")
                        await self.web_analyzer.capture_page_state("next_button_missing_on_challenge")
                        return False
                    await next_button_again.click()
                    self.logger.info("追加認証画面の「次へ」ボタンをクリックしました。")
                    await asyncio.sleep(1.5 + random.uniform(0.2, 0.8)) # 遷移待機

                    # 追加認証後、改めてパスワードフィールドを探す必要がある
                    self.logger.info("追加認証後、パスワード入力フィールドを再検索します。")
                    if await self._check_page_closed("追加認証後パスワード検索"): return False
                    password_input = await self.adaptive_selectors.find_input_by_any_attribute(
                         {
                             'name': ['password'],
                             'type': ['password'],
                             'autocomplete': ['current-password']
                         },
                         timeout=15000 # 再検索なので少し長めに待つ
                    )
                    if not password_input:
                         self.logger.error("追加認証後のパスワード入力フィールドが見つかりません。")
                         await self.web_analyzer.capture_page_state("password_input_missing_after_challenge")
                         return False
                     self.logger.info("追加認証後、パスワード入力フィールドを検出しました。")

                else:
                     # パスワードも追加認証も見つからない場合、2FAの可能性をチェック
                     self.logger.info("パスワード入力フィールドも追加認証フィールドも見つかりません。2FAの可能性をチェックします。")
                     if await self._check_page_closed("2FAチェック"): return False
                     if await self.handle_2fa():
                         # 2FA処理が成功した場合、この後のパスワード入力やログインボタンクリックは不要なことが多い
                         self.logger.info("2FA処理が成功しました。ログイン完了を確認します。")
                         password_input = None # ログインボタンクリックをスキップさせるフラグ
                     else:
                         # 2FAも見つからない場合、ログインフローが不明
                         self.logger.error("パスワード入力、追加認証、または2FAのいずれのフィールドも見つかりませんでした。ログインフローが変更された可能性があります。")
                         await self.web_analyzer.capture_page_state("password_or_challenge_or_2fa_missing")
                         return False

            # パスワードフィールドが見つかった（または追加認証後に見つかった）場合、入力する
            if password_input:
                 if await self._check_page_closed("パスワード入力"): return False
                 await password_input.fill(password)
                 await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))

                 # --- 「ログイン」ボタンクリック ---
                 self.logger.info("「ログイン」ボタンを検索・クリックします")
                 if await self._check_page_closed("「ログイン」ボタン検索"): return False
                 login_button = await self.adaptive_selectors.find_element_by_text_or_role(
                     texts=['ログイン', 'Log in'],
                     role='button',
                     data_testid=['ocfLoginButton', 'LoginForm_Login_Button', 'loginButton'], # Test ID候補追加
                     timeout=10000
                 )
                 if not login_button:
                     self.logger.error("「ログイン」ボタンが見つかりませんでした。")
                     await self.web_analyzer.capture_page_state("login_button_missing")
                     return False
                 await login_button.click()
                 self.logger.info("「ログイン」ボタンをクリックしました。")
                 await asyncio.sleep(3 + random.uniform(0.5, 1.5)) # ログイン完了と遷移を待つ

            # 2FAフローなどでパスワード入力がなかった場合は、既にログイン後の状態のはず
            elif password_input is None and not additional_input_handled: # 2FAフロー経由の場合
                 self.logger.info("2FA処理後のため、「ログイン」ボタンクリックはスキップします。ログイン後の状態確認へ。")
                 await asyncio.sleep(3 + random.uniform(0.5, 1.5)) # 状態安定待機

            # --- ログイン成功確認 ---
            try:
                self.logger.info("ログイン成功を確認します（タイムライン要素が表示されるか）。")
                if await self._check_page_closed("ログイン成功確認"): return False
                # タイムラインの主要カラムが表示されるかで判断
                await self.page.wait_for_selector(
                     '[data-testid="primaryColumn"], [role="main"]', # メインコンテンツ領域を示すセレクタ候補
                     timeout=25000 # ログイン後の読み込みは時間がかかる場合がある
                )
                self.logger.info("ログイン成功を確認しました（タイムライン要素検出）。")
                return True
            except PlaywrightTimeoutError as e:
                self.logger.error(f"ログイン成功確認中にタイムアウトしました。ログイン失敗またはUI変更の可能性があります。: {e}")
                # 失敗時の状態を記録
                await self.web_analyzer.capture_page_state("login_verification_failed")
                # 失敗原因の特定を試みる (例: エラーメッセージ表示確認)
                # error_message = await self.page.locator('[role="alert"], [data-testid="error-message"]').text_content(timeout=1000)
                # if error_message: self.logger.error(f"ログイン失敗メッセージ検出: {error_message}")
                return False

        except PlaywrightError as pe:
            # Playwright固有のエラー（ページクローズ、接続断など）
            if "close" in str(pe).lower() or "disconnect" in str(pe).lower() or "target" in str(pe).lower():
                self.logger.error(f"ログイン処理中にページや接続に関するPlaywrightエラーが発生しました: {pe}")
            else:
                self.logger.error(f"ログインプロセスで予期せぬPlaywrightエラーが発生しました: {pe}", exc_info=True)
            # エラー発生時の状態を保存（ページがまだ有効なら）
            if self.web_analyzer and self.page and not self.page.is_closed():
                await self.web_analyzer.capture_page_state("login_process_playwright_error")
            return False
        except Exception as e:
            self.logger.error(f"ログインプロセス全体で予期せぬエラーが発生しました: {e}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed():
                await self.web_analyzer.capture_page_state("login_process_unexpected_error")
            return False
        finally:
            self.logger.info("Twitter ログインプロセス終了")


    async def handle_2fa(self) -> bool:
        """
        2段階認証 (2FA) のコード入力画面を処理する。
        ユーザーにコンソールからコード入力を求める。

        Returns:
            bool: 2FAの処理が試行され、成功した（またはフィールドが見つからなかった）場合は True、
                  ユーザー入力失敗やエラーの場合は False。
        """
        if await self._check_page_closed("2FA処理"): return False
        assert self.page is not None # 型チェック用
        assert self.adaptive_selectors is not None

        self.logger.info("2段階認証 (2FA) の処理を試みます。")
        try:
            # 認証コード入力フィールドを探す
            verification_input = await self.adaptive_selectors.find_input_by_any_attribute(
                {
                    'name': ['challenge_response', 'text'], # name属性も考慮
                    'data-testid': ['ocfEnterTextTextInput', 'LoginVerificationCodeForm-challengeInput'],
                    'aria-label': ['認証コード', 'Verification code', '認証コードを確認', 'Verify authentication code']
                },
                timeout=7000 # 2FA画面が表示されるまで少し待つ
            )

            if verification_input:
                self.logger.info("2段階認証コード入力フィールドが見つかりました。")
                verification_code = ""
                try:
                    # isatty() でインタラクティブな環境か確認
                     if os.isatty(0):
                         print("--------------------------------------------------")
                         print("2段階認証コードが必要です。")
                         verification_code = input("認証コードを入力してください: ")
                         print("--------------------------------------------------")
                     else:
                         self.logger.error("非インタラクティブ環境のため、2FAコードを入力できません。")
                         return False # コード入力不可

                except EOFError:
                    self.logger.error("2FAコードの入力が取得できませんでした (EOFError)。")
                    return False
                except Exception as e:
                     self.logger.error(f"2FAコードの入力取得中にエラー: {e}")
                     return False

                if not verification_code:
                     self.logger.error("2FAコードが入力されませんでした。")
                     return False

                if await self._check_page_closed("2FAコード入力"): return False
                await verification_input.fill(verification_code)
                await asyncio.sleep(0.5 + random.uniform(0.1, 0.3))

                # 確認ボタン（次へ、認証など）をクリック
                if await self._check_page_closed("2FA確認ボタン検索"): return False
                confirm_button = await self.adaptive_selectors.find_element_by_text_or_role(
                    texts=['次へ', 'Next', '認証', 'Verify', '確認'], # 確認ボタンのテキスト候補
                    role='button',
                    data_testid=['ocfEnterTextNextButton', 'LoginVerificationCodeForm-submitButton'],
                    timeout=5000
                )
                if confirm_button:
                    await confirm_button.click()
                    self.logger.info("2FAコードを送信しました。")
                    await asyncio.sleep(2 + random.uniform(0.3, 0.7)) # 送信後の待機
                    return True # 2FAコードを送信できた時点で True とする
                else:
                    self.logger.warning("2FAコード送信ボタンが見つかりませんでした。手動での確認が必要かもしれません。")
                    # 送信ボタンが見つからなくても、コード入力自体は試みたのでTrueを返す場合もある（設計次第）
                    # ここでは見つからなかったら False とする
                    await self.web_analyzer.capture_page_state("2fa_confirm_button_missing")
                    return False
            else:
                # 2FA入力フィールドが見つからなかった場合
                self.logger.info("2段階認証コード入力フィールドは見つかりませんでした（2FA不要またはUI変更）。")
                return False # 2FAフィールドが見つからなければFalse（不要だったことを示す）

        except PlaywrightError as pe:
             self.logger.error(f"2FA処理中にPlaywrightエラーが発生しました: {pe}", exc_info=("closed" not in str(pe).lower()))
             if self.web_analyzer and self.page and not self.page.is_closed():
                 await self.web_analyzer.capture_page_state("handle_2fa_playwright_error")
             return False # エラー発生時はFalse
        except Exception as e:
            self.logger.error(f"2FA処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed():
                 await self.web_analyzer.capture_page_state("handle_2fa_unexpected_error")
            return False # エラー発生時はFalse

    async def scrape_tweets(self, query: str, max_tweets: int | None = None) -> list[dict]:
        """
        指定された検索クエリでツイートを検索し、スクロールしながら情報を収集する。

        Args:
            query (str): Twitterの検索クエリ (例: "#VRChat event", "from:elonmusk")。
            max_tweets (int | None, optional): 収集するツイートの最大件数。Noneの場合は制限なし。 Defaults to None.

        Returns:
            list[dict]: 収集されたツイート情報のリスト。各要素はツイートID, テキスト, URLなどを含む辞書。
                        エラー発生時は空リストを返す。
        """
        if await self._check_page_closed(f"ツイート収集開始 ({query})"): return []
        assert self.page is not None
        assert self.adaptive_selectors is not None
        assert self.web_analyzer is not None

        self.logger.info(f"ツイート検索とスクレイピングを開始します: Query='{query}', MaxTweets={max_tweets}")
        tweets_data = []
        seen_tweet_ids = set()

        try:
            # --- 検索実行 ---
            # タイムライン上の検索バーを探す
            self.logger.info("タイムライン上の検索バーを検索中...")
            if await self._check_page_closed("検索バー検索"): return []
            search_box = await self.adaptive_selectors.find_input_by_any_attribute(
                {
                    'data-testid': ['SearchBox_Search_Input', 'search-box-input'], # Test ID候補
                    'aria-label': ['検索クエリ', 'Search query', '検索', 'Search'] # Label候補
                },
                timeout=15000 # タイムライン読み込み後なので長めに待つ
            )

            if not search_box:
                # 検索バーが見つからない場合のフォールバック処理
                self.logger.warning(f"タイムライン上の検索バーが見つかりませんでした。UI変更の可能性。検索URLへの直接移動を試みます。 ({query})")
                if await self._check_page_closed("検索フォールバックURL移動"): return []
                # クエリをURLエンコード
                encoded_query = quote(query)
                # f=live で「最新」タブを指定 (f=top が「トップ」)
                search_url = f"https://twitter.com/search?q={encoded_query}&src=typed_query&f=live"
                self.logger.info(f"フォールバックURL: {search_url}")
                try:
                    await self.page.goto(search_url, wait_until="networkidle", timeout=60000)
                    # networkidle が不安定な場合があるので、追加で要素待機
                    await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                    self.logger.info("フォールバックURLへの遷移と最初のツイート読み込みを確認しました。")
                    await asyncio.sleep(2 + random.uniform(0.5, 1.0)) # 安定待機
                except (PlaywrightTimeoutError, PlaywrightError) as fallback_e:
                    self.logger.error(f"フォールバックURLへの遷移またはコンテンツ読み込みに失敗しました: {fallback_e}")
                    await self.web_analyzer.capture_page_state(f"search_fallback_goto_failed_{quote(query)[:50]}")
                    return [] # フォールバックも失敗したら諦める
            else:
                 # 検索バーが見つかった場合
                 self.logger.info(f"検索バーを検出。クエリ '{query}' を入力します。")
                 if await self._check_page_closed("検索クエリ入力"): return []
                 await search_box.fill(query)
                 await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))
                 self.logger.info("Enterキーを押下して検索を実行します。")
                 if await self._check_page_closed("検索実行 (Enter)"): return []
                 await search_box.press('Enter')

                 # 検索結果ページの読み込み待機
                 self.logger.info("検索結果ページの読み込みを待機中...")
                 try:
                     if await self._check_page_closed("検索結果待機"): return []
                     # URLが変化するか、検索結果特有の要素（最初のツイート）が表示されるのを待つ
                     await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                     # または await self.page.wait_for_url("**/search?**", timeout=30000)
                     self.logger.info("検索結果ページへの遷移と最初のツイート読み込みを確認しました。")
                     await asyncio.sleep(2 + random.uniform(0.5, 1.0)) # 安定待機
                 except (PlaywrightTimeoutError, PlaywrightError) as e:
                     self.logger.error(f"検索結果ページの読み込み待機中にエラーまたはタイムアウト: {e}")
                     await self.web_analyzer.capture_page_state(f"search_result_load_fail_{quote(query)[:50]}")
                     return []


            # --- スクロールとツイート抽出 ---
            self.logger.info(f"ツイートのスクロールと抽出を開始: {query}")
            scroll_attempts = 0
            max_scroll_attempts_no_change = 5 # スクロールしても高さが変わらない場合の最大試行回数
            consecutive_no_new_tweets = 0
            no_new_tweets_threshold = 3 # 新規ツイートが見つからない場合にスクロールを停止する閾値
            last_height = 0

            while True: # max_tweets に達するか、新規ツイートが見つからなくなるまでループ
                 if await self._check_page_closed("スクロールループ"): break
                 if max_tweets is not None and len(tweets_data) >= max_tweets:
                     self.logger.info(f"指定された最大ツイート数 ({max_tweets}) に達しました。")
                     break

                 # 現在表示されているツイート要素を取得
                 # 広告なども含まれる可能性があるため注意 (例: [data-testid="placementTracking"])
                 tweet_articles = await self.page.locator('article[data-testid="tweet"]').all()
                 self.logger.info(f"現在 {len(tweet_articles)} 件のツイート要素を検出 (うち新規探索対象)")

                 new_tweets_found_in_scroll = 0
                 for article in tweet_articles:
                     if await self._check_page_closed("ツイート要素処理"): break # 内側ループも抜ける
                     if max_tweets is not None and len(tweets_data) >= max_tweets: break # 最大数チェック

                     try:
                         # --- ツイート情報の抽出 ---
                         tweet_id = None
                         tweet_url = ""
                         user_handle = ""
                         user_name = ""
                         tweet_text = ""
                         tweet_date = ""

                         # 1. ツイートIDとURLの取得 (投稿時刻のリンクから取得するのが比較的安定)
                         # aタグで、hrefに '/status/' を含み、内部に time タグを持つものを探す
                         time_link_element = article.locator('a[href*="/status/"]:has(time)').first
                         if await time_link_element.count() > 0:
                             href = await time_link_element.get_attribute('href')
                             if href and "/status/" in href:
                                 parts = href.split('/status/')
                                 if len(parts) > 1:
                                     # URLからユーザーハンドルとツイートIDを抽出
                                     user_handle_from_url = parts[0].split('/')[-1]
                                     if user_handle_from_url:
                                         user_handle = f"@{user_handle_from_url}" # @マークを追加
                                     possible_id = parts[1].split('?')[0].split('/')[0] # 末尾の不要部分を除去
                                     if possible_id.isdigit():
                                         tweet_id = possible_id
                                         tweet_url = f"https://twitter.com{href}" # フルURL

                         # IDが取得できない、または既に追加済みのツイートはスキップ
                         if not tweet_id or tweet_id in seen_tweet_ids:
                             continue

                         # 2. ツイート本文 (data-testid="tweetText")
                         text_element = article.locator('[data-testid="tweetText"]').first
                         if await text_element.count() > 0:
                             tweet_text = await text_element.inner_text()
                         else:
                             # 本文が見つからないケースも考慮 (画像のみのツイートなど)
                             self.logger.debug(f"ツイート本文が見つかりません (ID: {tweet_id})")

                         # 3. 投稿日時 (time タグの datetime 属性)
                         time_element = article.locator('time').first
                         if await time_element.count() > 0:
                             tweet_date = await time_element.get_attribute("datetime") or "" # datetime属性がない場合も考慮

                         # 4. ユーザー名とハンドル名 (data-testid="User-Name" 周辺から抽出)
                         user_name_container = article.locator('[data-testid="User-Name"]').first
                         if await user_name_container.count() > 0:
                             # 表示名 (span > span 構造が多い)
                             name_element = user_name_container.locator('div > div > div > a > div > div > span > span').first # より具体的なセレクタ
                             if await name_element.count() == 0: # 代替セレクタ
                                  name_element = user_name_container.locator('span:not([dir]) span').first # dir属性を持たないspan内のspan

                             if await name_element.count() > 0:
                                 user_name = await name_element.inner_text()

                             # ハンドル名 (@を含むspan) - URLから取得したものを優先する場合もある
                             if not user_handle: # URLから取得できていない場合のみここで探す
                                 handle_element = user_name_container.locator('div[dir="ltr"] > span:has-text("@")').first
                                 if await handle_element.count() > 0:
                                     user_handle = await handle_element.inner_text() # @マーク付きで取得されるはず

                         # 抽出データを辞書に格納
                         tweet_data = {
                             "tweet_id": tweet_id,
                             "text": tweet_text.strip(),
                             "url": tweet_url,
                             "date": tweet_date,
                             "user_name": user_name.strip(),
                             "user_handle": user_handle.strip(), # @マーク付き (または空文字)
                             "query": query, # どのクエリで収集されたか
                             "scraped_timestamp": datetime.now().isoformat()
                             # 必要なら他の情報 (リツイート数、いいね数など) も追加
                             # reply_count = await article.locator('[data-testid="reply"]').text_content()
                             # retweet_count = await article.locator('[data-testid="retweet"]').text_content()
                             # like_count = await article.locator('[data-testid="like"]').text_content()
                             # view_count = await article.locator('a[href$="/analytics"] span span span').text_content() # 変わりやすい
                         }

                         tweets_data.append(tweet_data)
                         seen_tweet_ids.add(tweet_id)
                         new_tweets_found_in_scroll += 1

                     except PlaywrightError as pe_inner:
                          if "close" in str(pe_inner).lower(): raise pe_inner # ページクローズは上位に投げる
                          self.logger.warning(f"ツイート情報の抽出中にPlaywrightエラー (ID: {tweet_id if tweet_id else '不明'}): {pe_inner}", exc_info=False)
                     except Exception as e:
                         # 個別ツイートの抽出エラーは警告に留め、処理を続行
                         self.logger.warning(f"ツイート情報の抽出中に予期せぬエラー (ID: {tweet_id if tweet_id else '不明'}): {e}", exc_info=False) # トレースバックは抑制

                 # --- ループ中断・継続判定 ---
                 if self.page.is_closed(): break # ページが閉じていたらループ終了
                 if max_tweets is not None and len(tweets_data) >= max_tweets:
                      self.logger.info(f"指定された最大ツイート数 ({max_tweets}) に達しました (ループ内チェック)。")
                      break # ループ終了

                 self.logger.info(f"このスクロール処理で {new_tweets_found_in_scroll} 件の新規ツイートを追加。収集済み合計: {len(tweets_data)}")

                 # 新規ツイートが一定回数連続で見つからなければ終了
                 if new_tweets_found_in_scroll == 0:
                     consecutive_no_new_tweets += 1
                     self.logger.info(f"新規ツイートが見つからない連続回数: {consecutive_no_new_tweets}/{no_new_tweets_threshold}")
                     if consecutive_no_new_tweets >= no_new_tweets_threshold:
                         self.logger.info(f"新規ツイートが {no_new_tweets_threshold} 回連続で見つからなかったため、スクロールを終了します。")
                         break
                 else:
                     consecutive_no_new_tweets = 0 # 見つかればリセット


                 # --- ページをスクロール ---
                 current_height = await self.page.evaluate('document.body.scrollHeight')
                 if current_height == last_height:
                      scroll_attempts += 1
                      self.logger.info(f"スクロール高さ変わらず。試行: {scroll_attempts}/{max_scroll_attempts_no_change}")
                      if scroll_attempts >= max_scroll_attempts_no_change:
                          self.logger.info("スクロールしてもページの高さが変化しないため、終了します。")
                          break
                      # 高さが変わらない場合、少し長めに待ってから再試行
                      await asyncio.sleep(3 + random.uniform(0.5, 1.5))
                 else:
                      scroll_attempts = 0 # 高さが変わればリセット
                      last_height = current_height

                 # 実際にスクロール実行
                 await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
                 self.logger.info("ページを下にスクロールしました。")

                 # スクロール後のコンテンツ読み込み待機
                 try:
                     # networkidle は不安定な場合があるため、特定の要素の増加やローディングインジケータの消滅を待つ方が良い場合も
                     await self.page.wait_for_load_state('networkidle', timeout=10000) # 10秒待つ
                 except PlaywrightTimeoutError:
                     # タイムアウトしても、ある程度読み込まれている可能性があるので続行
                     self.logger.info("ネットワークアイドル待機タイムアウト。処理を続行します。")
                     # 追加で少し待つ
                     await asyncio.sleep(2 + random.uniform(0.3, 0.7))
                 except PlaywrightError as pe_scroll: # スクロール中のページクローズ等
                     if "close" in str(pe_scroll).lower() or "context closed" in str(pe_scroll).lower():
                         self.logger.error("スクロール待機中にページまたはコンテキストが閉じられました。")
                         break # ループ終了
                     else:
                         self.logger.warning(f"スクロール待機中にPlaywrightエラー: {pe_scroll}")
                         await asyncio.sleep(2) # エラーでも少し待つ

                 await asyncio.sleep(1 + random.uniform(0.5, 1.5)) # 各スクロール間のランダムなインターバル


            # --- スクロールループ終了 ---
            self.logger.info(f"ツイート検索・抽出完了: Query='{query}' - 合計 {len(tweets_data)} 件")
            return tweets_data

        except PlaywrightError as pe:
             # goto, wait_for_selector など、ループ外の処理で発生する可能性のあるエラー
            if "close" in str(pe).lower() or "disconnect" in str(pe).lower() or "context closed" in str(pe).lower():
                 self.logger.error(f"ツイート収集中にページ/コンテキストが予期せず閉じられたか、接続が切れました ({query}): {pe}")
            else:
                 self.logger.error(f"ツイート収集中にPlaywrightエラーが発生しました ({query}): {pe}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed():
                 await self.web_analyzer.capture_page_state(f"scrape_tweets_playwright_error_{quote(query)[:50]}")
            return [] # エラー時は空リスト
        except Exception as e:
             self.logger.error(f"ツイートのスクレイピング中に予期せぬエラーが発生しました ({query}): {e}", exc_info=True)
             if self.web_analyzer and self.page and not self.page.is_closed():
                  await self.web_analyzer.capture_page_state(f"scrape_tweets_unexpected_error_{quote(query)[:50]}")
             return [] # エラー時は空リスト


    async def save_data(self, data: list | dict, prefix: str) -> bool:
        """
        収集したデータをJSONファイルとして保存する。

        Args:
            data (list | dict): 保存するデータ (リストまたは辞書)。
            prefix (str): ファイル名のプレフィックス (例: "tweets_VRChat", "list_members_12345")。

        Returns:
            bool: 保存が成功したかどうか。
        """
        if not data:
            self.logger.warning(f"保存するデータが空です: Prefix='{prefix}'")
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # ファイル名に使えない文字を除去・置換し、長さを制限
        safe_prefix = "".join(x for x in prefix if x.isalnum() or x in ['_', '-'])[:100]
        filename = os.path.join(self.raw_data_dir, f"{safe_prefix}_{timestamp}.json")

        # データ形式の簡易チェック
        data_type_valid = False
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                # リストの場合、最初の要素に必要なキーがあるか簡易チェック (例)
                required_keys = ["tweet_id", "text", "url", "date"] # ツイートデータの場合の例
                if all(key in data[0] for key in required_keys):
                    self.logger.info(f"データ形式（ツイートリスト, {len(data)}件）を確認。")
                    data_type_valid = True
                else:
                    self.logger.warning(f"リスト内の最初の要素に必要なキーが欠けている可能性があります。Prefix='{prefix}', Keys={list(data[0].keys())}")
                    # キーがなくても保存は試みる
                    data_type_valid = True # 保存は試みる
            elif len(data) == 0:
                 self.logger.warning(f"保存データは空のリストです。Prefix='{prefix}'")
                 # 空リストもファイルとして保存する（後で処理しやすくするため）
                 data_type_valid = True
            else:
                 self.logger.error(f"リストの要素が辞書ではありません。保存を中止します。Prefix='{prefix}', Type={type(data[0])}")
                 return False
        elif isinstance(data, dict):
            self.logger.info(f"データ形式（辞書）を確認。Prefix='{prefix}'")
            data_type_valid = True
        else:
            self.logger.error(f"無効なデータ型です: {type(data)}。保存を中止します。Prefix='{prefix}'")
            return False

        if not data_type_valid: # 基本的にはここには到達しないはずだが念のため
             return False

        # ファイルへの書き込み
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            # 保存後のファイルサイズチェック（小さすぎないか確認）
            file_size = os.path.getsize(filename)
            if file_size  dict | None:
        """
        設定に基づいてスクレイピングタスク（ツイート検索、リスト収集など）を実行するメインメソッド。

        Args:
            headless_mode (bool, optional): ブラウザをヘッドレスで実行するかどうか。Defaults to False.
            proxy (dict | None, optional): 使用するプロキシ設定。Defaults to None.

        Returns:
            dict | None: 各ターゲットの収集結果を格納した辞書。エラー時はNone。
        """
        all_results = {}
        browser_initialized = False # ブラウザ初期化成功フラグ

        try:
            # --- 1. ブラウザ初期化 ---
            browser_initialized = await self.initialize_browser(headless=headless_mode, proxy_settings=proxy)
            if not browser_initialized:
                self.logger.error("ブラウザ初期化に失敗したため、スクレイピング処理を中止します。")
                return None # 初期化失敗時はNoneを返す

            # --- 2. ログイン ---
            login_success = await self.login_to_twitter()
            if not login_success:
                self.logger.error("ログインに失敗しました。スクレイピングを続行できません。")
                # ログイン失敗時の状態を分析・記録 (オプション)
                if self.web_analyzer and self.page and not self.page.is_closed():
                    await self.web_analyzer.capture_page_state("login_failed_final_state")
                    # await self.analyze_web_structure() # より詳細な分析が必要な場合
                return None # ログイン失敗時は終了

            self.logger.info("ログイン成功。スクレイピングターゲットの処理を開始します。")

            # --- 3. ターゲット処理 ---
            for i, target in enumerate(self.scraping_targets):
                 self.logger.info(f"ターゲット {i+1}/{len(self.scraping_targets)} の処理開始: {target}")
                 if await self._check_page_closed(f"ターゲット {i+1} 処理開始"): break # ページが閉じていたらループ中断

                 target_processed = False
                 # クエリ検索ターゲット
                 if 'query' in target:
                     query = target['query']
                     max_tweets = target.get('max_tweets') # ターゲットごとに最大件数を指定可能にする
                     self.logger.info(f"タイプ: クエリ検索, Query: {query}, MaxTweets: {max_tweets}")
                     try:
                         tweets = await self.scrape_tweets(query, max_tweets=max_tweets)
                         if tweets:
                             # ファイル名用にクエリから特殊文字を除去・短縮
                             safe_query_name = quote(query).replace('%', '_')[:50] # URLエンコードして一部を使用
                             save_success = await self.save_data(tweets, f"tweets_{safe_query_name}")
                             if save_success:
                                 all_results[f"query_{query}"] = {"status": "success", "count": len(tweets)}
                             else:
                                  all_results[f"query_{query}"] = {"status": "save_failed", "count": len(tweets)}
                         else:
                             self.logger.warning(f"クエリ '{query}' でツイートが収集できませんでした（0件またはエラー）。")
                             all_results[f"query_{query}"] = {"status": "no_data_or_error", "count": 0}
                         target_processed = True
                     except Exception as e_query:
                          self.logger.error(f"クエリ '{query}' の処理中にエラー: {e_query}", exc_info=True)
                          all_results[f"query_{query}"] = {"status": "processing_error"}


                 # リスト収集ターゲット (list_collector.py を使う想定)
                 elif 'list_url' in target:
                     list_url = target['list_url']
                     self.logger.info(f"タイプ: リスト収集 (未実装), URL: {list_url}")
                     # --- ここに list_collector を呼び出すロジックを実装 ---
                     # 例:
                     try:
                         # list_collector モジュールを動的にインポート (必要に応じて)
                         # import importlib
                         # list_collector_module = importlib.import_module("src.data_collection.list_collector")
                         # ListCollectorClass = getattr(list_collector_module, "TwitterListInfoCollector")

                         # # ListCollector インスタンスを作成し、必要なオブジェクトを渡す
                         # list_collector = ListCollectorClass(self.config_manager, self.logger)
                         # list_collector.page = self.page # 共有ページオブジェクト
                         # list_collector.context = self.context
                         # list_collector.adaptive_selectors = self.adaptive_selectors
                         # list_collector.web_analyzer = self.web_analyzer
                         # # list_collector.cache = self.cache # 必要ならキャッシュも共有

                         # # 収集実行 ( collect_list_members_and_profiles のようなメソッドを想定)
                         # # members_data = await list_collector.collect_list_members_and_profiles(list_url) # 仮のメソッド名
                         members_data = None # 未実装のため None
                         if members_data:
                             list_id = list_url.split('/')[-1]
                             save_success = await self.save_data(members_data, f"list_members_{list_id}")
                             if save_success:
                                 all_results[f"list_{list_url}"] = {"status": "success", "count": len(members_data)}
                             else:
                                  all_results[f"list_{list_url}"] = {"status": "save_failed", "count": len(members_data)}
                         else:
                              # self.logger.warning(f"リスト '{list_url}' の収集に失敗またはデータがありませんでした。")
                              all_results[f"list_{list_url}"] = {"status": "not_implemented", "count": 0} # 未実装ステータス
                         target_processed = True # 処理を試みたフラグ

                     # except ImportError:
                     #      self.logger.error("list_collector モジュールが見つかりません。リスト収集をスキップします。")
                     #      all_results[f"list_{list_url}"] = {"status": "module_not_found"}
                     except Exception as e_list:
                         self.logger.error(f"リスト '{list_url}' の処理中にエラー: {e_list}", exc_info=True)
                         all_results[f"list_{list_url}"] = {"status": "processing_error"}
                         # エラーが発生しても次のターゲットへ進む

                 # その他のターゲットタイプ
                 else:
                     self.logger.warning(f"未対応のターゲットタイプです: {target}")
                     all_results[str(target)] = {"status": "unsupported_type"}
                     target_processed = True # 未対応でも処理済みとする

                 # ターゲット間のインターバル (レート制限対策)
                 if target_processed and i  dict:
        """
        現在のページのウェブ構造を分析する (WebStructureAnalyzerへのラッパー)。

        Returns:
            dict: 分析結果。
        """
        if await self._check_page_closed("構造分析"): return {"error": "Page is closed"}

        if self.web_analyzer:
            self.logger.info("ウェブ構造分析を開始します。")
            return await self.web_analyzer.analyze_web_structure()
        else:
            self.logger.warning("WebStructureAnalyzerが初期化されていません。")
            return {"error": "Analyzer not initialized"}


# --- 実行ブロック ---
if __name__ == "__main__":
    import random # ランダム待機用

    # --- ロガー設定 ---
    # mainレベルでも設定しておくと、クラス初期化前のエラーもファイルに出力される可能性がある
    log_filename = "twitter_scraper_main.log"
    logging.basicConfig(
        level=logging.INFO, # INFOレベル以上を記録
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'), # ファイル出力
            logging.StreamHandler() # コンソール出力
        ]
    )
    main_logger = logging.getLogger("MainExecutor") # このファイル用のロガー名

    # --- 設定 ---
    # 実際には configuration_manager.py を使う
    config_manager = ConfigManager() # 仮のConfigManagerを使用

    # --- スクレイパーインスタンス生成 ---
    scraper = EnhancedTwitterScraper(config_manager, logger=main_logger) # メインロガーを渡す

    # --- 非同期処理実行 ---
    try:
        main_logger.info("スクレイピング処理を開始します...")
        # asyncio.run() で非同期の main メソッドを実行
        # ヘッドレスモードで実行する場合は run_headless=True を指定
        # プロキシを使用する場合は use_proxy={'server': 'http://your_proxy:port'} のように指定
        asyncio.run(scraper.main(run_headless=False, use_proxy=None))

        main_logger.info("スクレイピング処理が終了しました。")

    except KeyboardInterrupt:
        main_logger.info("\n処理がユーザーによって中断されました。")
    except Exception as e:
        # ここで捕捉されなかった予期せぬエラー
        main_logger.error(f"メイン実行ブロックで未捕捉のエラーが発生しました: {e}", exc_info=True)

```


## list\_collector.py

```python
import asyncio
import json
import os
import time
import logging
import re
from datetime import datetime
from urllib.parse import quote # URLエンコード用

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    Page, # 型ヒント用
    BrowserContext, # 型ヒント用
    Locator # 型ヒント用
)

# --- 依存関係 ---
# プロジェクト構成に合わせて実際のモジュールをインポートする
try:
    from src.common.web_structure_analyzer import WebStructureAnalyzer
    from src.common.adaptive_selectors import AdaptiveSelectors
    from src.common.configuration_manager import ConfigurationManager # 設定管理クラス
    from src.common.simple_cache import SimpleCache # キャッシュクラス
except ImportError as e:
     # もし __main__ で実行する場合など、相対インポートがうまくいかない場合を考慮
     print(f"依存モジュールのインポートに失敗しました: {e}")
     print("仮のクラス定義を使用します。")
     # --- ↓↓↓ 仮の依存クラス (動作確認用、通常は上記インポートを使用) ↓↓↓ ---
     class WebStructureAnalyzer:
         """仮のWebStructureAnalyzerクラス"""
         def __init__(self, page, logger, debug_data_dir='data/debug_data/'): self.page = page; self.logger = logger; os.makedirs(debug_data_dir, exist_ok=True)
         async def capture_page_state(self, state_name): self.logger.info(f"仮: ページ状態キャプチャ ({state_name})")
         async def analyze_web_structure(self): self.logger.info("仮: 構造分析実行"); return {}

     class AdaptiveSelectors:
         """仮のAdaptiveSelectorsクラス"""
         def __init__(self, page, logger): self.page = page; self.logger = logger
         async def find_input_by_any_attribute(self, attributes: dict, timeout=10000): self.logger.info(f"仮: find_input_by_any_attribute ({attributes})"); return None # 仮実装
         async def find_element_by_text_or_role(self, texts=None, role=None, data_testid=None, timeout=10000, exact_text=False): self.logger.info(f"仮: find_element_by_text_or_role"); return None # 仮実装

     class SimpleCache:
         """仮のSimpleCacheクラス"""
         def __init__(self, cache_dir='cache', logger=None): self.logger = logger or logging.getLogger(__name__); os.makedirs(cache_dir, exist_ok=True)
         def get(self, key): self.logger.info(f"仮: キャッシュ取得 ({key})"); return None
         def set(self, key, data): self.logger.info(f"仮: キャッシュ設定 ({key})")

     class ConfigManager:
         """仮のConfigManagerクラス"""
         def get(self, key, default=None):
             if key == 'scraping_targets': return [{'list_url': 'https://twitter.com/i/lists/1680272194977630208'}] # テスト用リストURL
             return default
     # --- ↑↑↑ 仮の依存クラスここまで ↑↑↑ ---


class TwitterListInfoCollector:
    """
    Playwrightを使用してTwitter (X) のリストからメンバー情報を収集し、
    各メンバーのプロフィール情報をスクレイピングするクラス。
    """
    def __init__(self, config_manager: ConfigManager, logger: logging.Logger | None = None):
        """
        TwitterListInfoCollectorを初期化する。

        Args:
            config_manager (ConfigManager): 設定管理オブジェクト。
            logger (logging.Logger | None, optional): ログ出力用のロガー。 Defaults to None (新規作成).
        """
        self.config_manager = config_manager

        # ロガー設定
        if logger is None:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler("twitter_list_collector.log", encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger

        # 設定値の取得
        self.scraping_targets = self.config_manager.get('scraping_targets', [])
        # self.credentials = self.config_manager.get('twitter_credentials', {})

        # ディレクトリ設定
        self.raw_data_dir = self.config_manager.get('raw_data_dir', 'data/raw_scraped_data/')
        self.debug_data_dir = self.config_manager.get('debug_data_dir', 'data/debug_data/')
        for directory in [self.raw_data_dir, self.debug_data_dir]:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                self.logger.error(f"ディレクトリ作成失敗: {directory}, エラー: {e}")

        # 依存オブジェクトの初期化
        self.cache = SimpleCache(cache_dir=self.config_manager.get('cache_dir', 'cache/profiles'), logger=self.logger) # プロフィール用キャッシュ

        # Playwright関連オブジェクト
        self.playwright: async_playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        # 依存クラスのインスタンス (ブラウザ初期化後に生成)
        self.web_analyzer: WebStructureAnalyzer | None = None
        self.adaptive_selectors: AdaptiveSelectors | None = None

    # --- ブラウザ初期化、クローズ、ログイン、2FA処理 ---
    # playwright_scraper.py とほぼ同じメソッドをこちらにも実装
    # (共通化のために BaseScraper クラスなどを作るのが望ましい)

    async def initialize_browser(self, headless: bool = False, proxy_settings: dict | None = None) -> bool:
        """Playwrightブラウザを初期化する (playwright_scraper.pyと同様)"""
        # (実装は playwright_scraper.py の initialize_browser と同じ)
        # ... (コード省略、上記 playwright_scraper.py の実装を参照) ...
        try:
            self.logger.info(f"Playwright ブラウザ初期化開始 (Headless: {headless})")
            self.playwright = await async_playwright().start()
            browser_launch_options = { 'headless': headless, 'args': ['--disable-blink-features=AutomationControlled','--start-maximized','--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-extensions','--disable-plugins-discovery','--disable-infobars'] }
            if proxy_settings: browser_launch_options['proxy'] = proxy_settings
            self.browser = await self.playwright.chromium.launch(**browser_launch_options)
            context_options = { 'user_agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36", 'viewport': {"width": 1920, "height": 1080}, 'locale': "ja-JP", 'timezone_id': "Asia/Tokyo", 'geolocation': {"latitude": 35.6895, "longitude": 139.6917}, 'permissions': ["geolocation"], 'color_scheme': "no-preference", 'device_scale_factor': 1.0 }
            self.context = await self.browser.new_context(**context_options)
            await self.context.add_init_script("""
                if (navigator.webdriver) { Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); }
                if (window.navigator.chrome) { window.navigator.chrome = { runtime: {} }; }
                if (window.chrome) { window.chrome = { app: { isInstalled: false }, runtime: {} }; }
                if (Notification && Notification.permission) { const op = Notification.permission; Object.defineProperty(Notification, 'permission', { get: () => op === 'denied' ? 'denied' : 'default', configurable: true }); }
                try { Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'], configurable: true }); } catch (e) {}
            """)
            self.page = await self.context.new_page()
            self.web_analyzer = WebStructureAnalyzer(self.page, self.logger, self.debug_data_dir)
            self.adaptive_selectors = AdaptiveSelectors(self.page, self.logger)
            self.logger.info("検出対策済みブラウザを初期化しました")
            return True
        except Exception as e:
            self.logger.error(f"ブラウザ初期化中にエラー: {e}", exc_info=True)
            await self.close_browser()
            return False


    async def close_browser(self):
        """Playwright関連リソースを閉じる (playwright_scraper.pyと同様)"""
        # (実装は playwright_scraper.py の close_browser と同じ)
        # ... (コード省略、上記 playwright_scraper.py の実装を参照) ...
        self.logger.info("ブラウザ関連リソースのクローズ処理を開始します。")
        if hasattr(self, 'page') and self.page and not self.page.is_closed():
            try: await self.page.close(); self.logger.info("ページを閉じました。")
            except Exception as e: self.logger.error(f"ページ終了エラー: {e}")
        self.page = None
        if hasattr(self, 'context') and self.context:
            try: await self.context.close(); self.logger.info("コンテキストを閉じました。")
            except Exception as e:
                 if "context closed" not in str(e).lower(): self.logger.error(f"コンテキスト終了エラー: {e}")
                 else: self.logger.debug(f"コンテキスト既にクローズ済: {e}")
        self.context = None
        if hasattr(self, 'browser') and self.browser and self.browser.is_connected():
            try: await self.browser.close(); self.logger.info("ブラウザを閉じました。")
            except Exception as e: self.logger.error(f"ブラウザ終了エラー: {e}")
        self.browser = None
        if hasattr(self, 'playwright') and self.playwright:
            try: await self.playwright.stop(); self.logger.info("Playwrightを停止しました。")
            except Exception as e: self.logger.error(f"Playwright終了エラー: {e}")
        self.playwright = None
        self.logger.info("ブラウザ関連リソースのクローズ処理完了。")


    async def _check_page_closed(self, operation_name: str) -> bool:
        """処理実行前にページが閉じられていないか確認するヘルパー"""
        if not self.page or self.page.is_closed():
            self.logger.error(f"{operation_name} を実行できません: ページが閉じられています。")
            return True
        return False

    async def login_to_twitter(self) -> bool:
        """Twitterにログインする (playwright_scraper.pyと同様)"""
        # (実装は playwright_scraper.py の login_to_twitter と同じ)
        # ... (コード省略、上記 playwright_scraper.py の実装を参照) ...
        if await self._check_page_closed("Twitterログイン"): return False
        assert self.page and self.adaptive_selectors and self.web_analyzer # 初期化確認
        self.logger.info("Twitter ログインプロセス開始")
        username = os.environ.get("TWITTER_USERNAME"); password = os.environ.get("TWITTER_PASSWORD")
        if not username or not password:
             try: import keyring; username = keyring.get_password("twitter", "username"); password = keyring.get_password("twitter", "password"); self.logger.info("keyring使用")
             except Exception: pass # keyringエラーは無視して次へ
        if not username or not password:
             try:
                  if os.isatty(0): username = input("ユーザー名: "); password = input("パスワード: ")
                  else: self.logger.warning("非インタラクティブ環境のため入力スキップ"); return False
             except EOFError: self.logger.error("入力EOFError"); return False
        if not username or not password: self.logger.error("認証情報なし"); return False
        self.logger.info(f"ユーザー名: {username}, パスワード: {'*' * len(password)}")

        try:
             await self.page.goto("https://twitter.com/login", wait_until="domcontentloaded", timeout=60000)
             await self.page.wait_for_selector('input[name="text"], input[autocomplete="username"]', timeout=30000)
             username_input = await self.adaptive_selectors.find_input_by_any_attribute({'name': ['text'],'autocomplete': ['username'],'aria-label': ['電話番号、メールアドレス、またはユーザー名','Phone, email address, or username'],'type': ['text', 'email']}, timeout=15000)
             if not username_input: self.logger.error("ユーザー名入力見つからず"); return False
             await username_input.fill(username); await asyncio.sleep(0.6)
             next_button = await self.adaptive_selectors.find_element_by_text_or_role(texts=['次へ', 'Next'],role='button',data_testid=['ocfEnterTextNextButton', 'next_link'],timeout=10000)
             if not next_button: self.logger.error("「次へ」ボタン見つからず"); return False
             await next_button.click(); await asyncio.sleep(1.6)

             password_input = None; additional_input_handled = False
             try: password_input = await self.adaptive_selectors.find_input_by_any_attribute({'name': ['password'],'type': ['password'],'autocomplete': ['current-password']}, timeout=10000)
             except PlaywrightTimeoutError: pass # 見つからなければ次へ

             if not password_input:
                  additional_input = await self.adaptive_selectors.find_input_by_any_attribute({'data-testid': ['ocfEnterTextTextInput', 'challenge_response'],'name': ['text', 'challenge_response'],'aria-label': ['電話番号またはユーザー名', 'Phone number or username']}, timeout=7000)
                  if additional_input:
                       self.logger.warning("追加認証要求あり"); await additional_input.fill(username); await asyncio.sleep(0.6); additional_input_handled = True
                       next_button_again = await self.adaptive_selectors.find_element_by_text_or_role(texts=['次へ', 'Next'], role='button', data_testid=['ocfEnterTextNextButton'], timeout=10000)
                       if not next_button_again: self.logger.error("追加認証「次へ」見つからず"); return False
                       await next_button_again.click(); await asyncio.sleep(1.6)
                       password_input = await self.adaptive_selectors.find_input_by_any_attribute({'name': ['password'], 'type': ['password'], 'autocomplete': ['current-password']}, timeout=15000)
                       if not password_input: self.logger.error("追加認証後パスワード見つからず"); return False
                  elif await self.handle_2fa(): password_input = None # 2FA成功
                  else: self.logger.error("パスワード/追加認証/2FA見つからず"); return False

             if password_input:
                  await password_input.fill(password); await asyncio.sleep(0.6)
                  login_button = await self.adaptive_selectors.find_element_by_text_or_role(texts=['ログイン', 'Log in'],role='button',data_testid=['ocfLoginButton', 'LoginForm_Login_Button'],timeout=10000)
                  if not login_button: self.logger.error("「ログイン」ボタン見つからず"); return False
                  await login_button.click(); await asyncio.sleep(3.5)
             elif password_input is None and not additional_input_handled: await asyncio.sleep(3.5) # 2FAフロー後

             await self.page.wait_for_selector('[data-testid="primaryColumn"], [role="main"]', timeout=25000)
             self.logger.info("ログイン成功を確認しました。")
             return True
        except Exception as e:
             self.logger.error(f"ログインプロセス中にエラー: {e}", exc_info=True)
             if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state("login_process_error")
             return False
        finally: self.logger.info("ログイン試行プロセス終了")


    async def handle_2fa(self) -> bool:
        """2段階認証を処理する (playwright_scraper.pyと同様)"""
        # (実装は playwright_scraper.py の handle_2fa と同じ)
        # ... (コード省略、上記 playwright_scraper.py の実装を参照) ...
        if await self._check_page_closed("2FA処理"): return False
        assert self.page and self.adaptive_selectors # 初期化確認
        self.logger.info("2FA処理試行")
        try:
             verification_input = await self.adaptive_selectors.find_input_by_any_attribute({'name': ['challenge_response', 'text'],'data-testid': ['ocfEnterTextTextInput', 'LoginVerificationCodeForm-challengeInput'],'aria-label': ['認証コード', 'Verification code']}, timeout=7000)
             if verification_input:
                  self.logger.info("2FAコード入力フィールド発見")
                  verification_code = "";
                  try:
                       if os.isatty(0): verification_code = input("2FAコード: ")
                       else: self.logger.error("非インタラクティブ環境で2FA不可"); return False
                  except EOFError: self.logger.error("2FA入力EOFError"); return False
                  if not verification_code: self.logger.error("2FAコード未入力"); return False
                  await verification_input.fill(verification_code); await asyncio.sleep(0.6)
                  confirm_button = await self.adaptive_selectors.find_element_by_text_or_role(texts=['次へ', 'Next', '認証', 'Verify'],role='button',data_testid=['ocfEnterTextNextButton', 'LoginVerificationCodeForm-submitButton'],timeout=5000)
                  if confirm_button: await confirm_button.click(); self.logger.info("2FAコード送信"); await asyncio.sleep(2.5); return True
                  else: self.logger.warning("2FA確認ボタン見つからず"); return False # 送信できなければFalse
             else: self.logger.info("2FAフィールド見つからず（不要かUI変更）"); return False # 不要だった場合はFalse
        except Exception as e: self.logger.error(f"2FA処理エラー: {e}", exc_info=True); return False


    async def collect_list_members(self, list_url: str, max_members: int | None = None) -> list[str]:
        """
        指定されたTwitterリストURLからメンバーのプロフィールURLを収集する。

        Args:
            list_url (str): 収集対象のリストURL (例: "https://twitter.com/i/lists/12345")。
            max_members (int | None, optional): 収集するメンバー数の上限。Noneの場合は制限なし。 Defaults to None.

        Returns:
            list[str]: 収集されたメンバーのプロフィールURLのリスト。エラー時は空リスト。
        """
        if await self._check_page_closed(f"リストメンバー収集開始 ({list_url})"): return []
        assert self.page is not None
        assert self.web_analyzer is not None

        self.logger.info(f"リストメンバー収集開始: URL='{list_url}', MaxMembers={max_members}")
        member_profile_urls = set()
        seen_handles = set() # ハンドル名で重複チェック (URLが微妙に変わる可能性考慮)

        try:
            # リストページに移動
            self.logger.info(f"リストページに移動します: {list_url}")
            if await self._check_page_closed("リストページへの移動"): return []
            await self.page.goto(list_url, wait_until="networkidle", timeout=60000)
            # networkidle後に追加でリストの要素が表示されるのを待つ
            await self.page.wait_for_selector('[data-testid="UserCell"]', timeout=30000)
            self.logger.info("リストページ読み込み完了、メンバー抽出開始")
            await asyncio.sleep(2 + random.uniform(0.5, 1.0)) # 安定待機

            # スクロールしてメンバーを収集
            scroll_attempts = 0
            max_scroll_attempts_no_change = 5 # スクロールしても変化がない場合の試行回数
            consecutive_no_new_members = 0
            no_new_members_threshold = 5 # 新規メンバーが見つからない場合に停止する閾値
            last_height = 0

            while True:
                 if await self._check_page_closed("リストメンバー収集スクロールループ"): break
                 if max_members is not None and len(member_profile_urls) >= max_members:
                      self.logger.info(f"指定された最大メンバー数 ({max_members}) に達しました。")
                      break

                 # 現在表示されているメンバーセルを取得
                 member_cells = await self.page.locator('[data-testid="UserCell"]').all()
                 self.logger.info(f"現在 {len(member_cells)} 件のユーザーセルを検出")

                 new_members_found_in_scroll = 0
                 for cell in member_cells:
                     if await self._check_page_closed("ユーザーセル処理"): break
                     if max_members is not None and len(member_profile_urls) >= max_members: break

                     try:
                         # プロフィールへのリンク (aタグのhref) を取得
                         # UserCell内の primaryAction ボタンや、ユーザー名部分のリンクなど
                         link_element = cell.locator('a[href^="/"][role="link"]:has([data-testid*="User"])').first # ユーザー名部分のリンク
                         if await link_element.count() == 0: # 代替セレクタ
                              link_element = cell.locator('[data-testid="UserCell"] > div > div > div > div > a').first

                         href = await link_element.get_attribute('href')
                         if not href or href == "/" or "/i/" in href or "/settings" in href: # 不要なリンクを除外
                              continue

                         profile_url = f"https://twitter.com{href.split('?')[0]}" # クエリパラメータを除去

                         # ハンドル名 (@を含むspan) で重複チェック
                         user_handle = ""
                         handle_element = cell.locator('div[dir="ltr"] > span:has-text("@")').first
                         if await handle_element.count() > 0:
                              handle_text = await handle_element.inner_text()
                              if handle_text.startswith("@"):
                                   user_handle = handle_text

                         # ハンドル名が取得でき、かつ未収集の場合に追加
                         if user_handle and user_handle not in seen_handles:
                              member_profile_urls.add(profile_url)
                              seen_handles.add(user_handle)
                              new_members_found_in_scroll += 1
                         # ハンドル名が取れなくてもURLが新しければ追加 (フォールバック)
                         elif profile_url not in member_profile_urls and user_handle not in seen_handles:
                              self.logger.debug(f"ハンドル名不明だが新規URLとして追加: {profile_url}")
                              member_profile_urls.add(profile_url)
                              # この場合、seen_handles に何を追加するか？ -> URLを仮登録？ or 何もしない
                              new_members_found_in_scroll += 1


                     except PlaywrightError as pe_cell:
                          if "close" in str(pe_cell).lower(): raise pe_cell
                          self.logger.warning(f"リストメンバーセルからの情報抽出中にPlaywrightエラー: {pe_cell}", exc_info=False)
                     except Exception as e:
                          self.logger.warning(f"リストメンバーセルからの情報抽出中に予期せぬエラー: {e}", exc_info=False)

                 # --- ループ中断・継続判定 ---
                 if self.page.is_closed(): break
                 if max_members is not None and len(member_profile_urls) >= max_members:
                      self.logger.info(f"指定された最大メンバー数 ({max_members}) に達しました (ループ内チェック)。")
                      break

                 self.logger.info(f"このスクロール処理で {new_members_found_in_scroll} 件の新規メンバーURLを追加。収集済み合計: {len(member_profile_urls)}")

                 if new_members_found_in_scroll == 0:
                     consecutive_no_new_members += 1
                     self.logger.info(f"新規メンバーURLが見つからない連続回数: {consecutive_no_new_members}/{no_new_members_threshold}")
                     if consecutive_no_new_members >= no_new_members_threshold:
                         self.logger.info(f"新規メンバーURLが {no_new_members_threshold} 回連続で見つからなかったため、スクロールを終了します。")
                         break
                 else:
                     consecutive_no_new_members = 0


                 # --- ページをスクロール ---
                 current_height = await self.page.evaluate('document.body.scrollHeight')
                 if current_height == last_height:
                      scroll_attempts += 1
                      self.logger.info(f"スクロール高さ変わらず（リスト）。試行: {scroll_attempts}/{max_scroll_attempts_no_change}")
                      if scroll_attempts >= max_scroll_attempts_no_change:
                          self.logger.info("スクロールしてもリストの高さが変化しないため、終了します。")
                          break
                      await asyncio.sleep(4 + random.uniform(0.5, 1.5)) # 長めに待機
                 else:
                      scroll_attempts = 0
                      last_height = current_height

                 await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
                 self.logger.info("リストページを下にスクロールしました。")

                 # スクロール後の待機
                 try:
                     await self.page.wait_for_load_state('networkidle', timeout=15000) # リスト読み込みは少し長めに待つ
                 except PlaywrightTimeoutError:
                     self.logger.info("ネットワークアイドル待機タイムアウト（リスト）。処理を続行します。")
                     await asyncio.sleep(3 + random.uniform(0.3, 0.7)) # 追加待機
                 except PlaywrightError as pe_scroll:
                     if "close" in str(pe_scroll).lower(): self.logger.error("リストスクロール待機中にページクローズ"); break
                     else: self.logger.warning(f"リストスクロール待機エラー: {pe_scroll}"); await asyncio.sleep(3)

                 await asyncio.sleep(1.5 + random.uniform(0.5, 1.0)) # スクロール間隔


            # --- スクロールループ終了 ---
            self.logger.info(f"リストメンバーURL収集完了: URL='{list_url}' - 合計 {len(member_profile_urls)} 件")
            return list(member_profile_urls)

        except PlaywrightError as pe:
            if "close" in str(pe).lower(): self.logger.error(f"リストメンバー収集中にページが予期せず閉じられました ({list_url}): {pe}")
            else: self.logger.error(f"リストメンバー収集中にPlaywrightエラー ({list_url}): {pe}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state(f"collect_list_members_playwright_error_{list_url.split('/')[-1]}")
            return []
        except Exception as e:
            self.logger.error(f"リストメンバー収集中に予期せぬエラー ({list_url}): {e}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state(f"collect_list_members_unexpected_error_{list_url.split('/')[-1]}")
            return []


    async def scrape_profile_info(self, profile_url: str) -> dict | None:
        """
        指定されたプロフィールURLからユーザー情報を収集する。
        キャッシュが存在する場合はキャッシュから返す。

        Args:
            profile_url (str): 収集対象のプロフィールURL。

        Returns:
            dict | None: 収集されたプロフィール情報 (名前, ハンドル, bio, フォロー数など)。
                         エラー発生または情報取得不可の場合は None。
        """
        self.logger.info(f"プロフィール情報収集開始: {profile_url}")

        # キャッシュチェック
        cache_key = profile_url # URL自体をキーとする
        cached_data = self.cache.get(cache_key)
        if cached_data:
            self.logger.info(f"キャッシュヒット: {profile_url}")
            # キャッシュデータに必要なキーがあるか念のため確認
            required_keys = ["profile_url", "user_handle", "user_name", "bio"]
            if isinstance(cached_data, dict) and all(key in cached_data for key in required_keys):
                return cached_data
            else:
                self.logger.warning(f"キャッシュデータが不完全です。再取得します: {profile_url}")


        # --- キャッシュがない場合、スクレイピング実行 ---
        if await self._check_page_closed(f"プロフィール収集開始 ({profile_url})"): return None
        assert self.page is not None
        assert self.web_analyzer is not None

        profile_info = {"profile_url": profile_url} # 初期化

        try:
            # プロフィールページに移動
            self.logger.info(f"プロフィールページに移動: {profile_url}")
            if await self._check_page_closed("プロフィールページへの移動"): return None
            await self.page.goto(profile_url, wait_until="networkidle", timeout=60000)
            # プロフィールヘッダーが表示されるのを待つ
            await self.page.wait_for_selector('[data-testid="UserProfileHeader_Items"], [data-testid*="UserName"]', timeout=30000)
            self.logger.info("プロフィールページ読み込み完了、情報抽出開始")
            await asyncio.sleep(1 + random.uniform(0.2, 0.5)) # 安定待機

            # --- 情報抽出 ---
            if await self._check_page_closed("プロフィール情報抽出"): return None

            # ユーザー名 (表示名)
            user_name = ""
            try:
                # セレクタ調整: data-testidが変動する可能性があるため、構造に依存したセレクタも試す
                name_locator = self.page.locator('[data-testid="UserName"] div[dir="ltr"] span > span').first # 標準的？
                if await name_locator.count() == 0:
                     name_locator = self.page.locator('div[data-testid^="UserAvatar-Container-"] + div > div > div[dir="ltr"] > span > span').first # 構造依存
                if await name_locator.count() > 0:
                     user_name = await name_locator.inner_text()
                profile_info["user_name"] = user_name.strip()
            except Exception as e_name: self.logger.warning(f"表示名の抽出エラー ({profile_url}): {e_name}")

            # ユーザーハンドル (@xxxx)
            user_handle = ""
            try:
                 handle_locator = self.page.locator('[data-testid="UserName"] div[dir="auto"] span:has-text("@")').first # 標準的？
                 if await handle_locator.count() == 0:
                      handle_locator = self.page.locator('div[data-testid^="UserAvatar-Container-"] + div > div > div[dir="auto"] span:has-text("@")').first # 構造依存
                 if await handle_locator.count() > 0:
                      user_handle = await handle_locator.inner_text()
                 profile_info["user_handle"] = user_handle.strip()
            except Exception as e_handle: self.logger.warning(f"ハンドル名の抽出エラー ({profile_url}): {e_handle}")

            # Bio (自己紹介文)
            bio = ""
            try:
                bio_locator = self.page.locator('[data-testid="UserDescription"]').first
                if await bio_locator.count() > 0:
                    bio = await bio_locator.inner_text()
                profile_info["bio"] = bio.strip()
            except Exception as e_bio: self.logger.warning(f"Bioの抽出エラー ({profile_url}): {e_bio}")


            # 場所、ウェブサイト、参加日
            location = ""; website = ""; join_date = ""
            try:
                # ヘッダーアイテム全体 (data-testid="UserProfileHeader_Items") を取得
                header_items_container = self.page.locator('[data-testid="UserProfileHeader_Items"]').first
                if await header_items_container.count() > 0:
                    # 各アイテム (span要素が多い) を反復処理
                    items_text = await header_items_container.locator('span').all_inner_texts()
                    items_elements = await header_items_container.locator('span').all()

                    for i, text in enumerate(items_text):
                        elem = items_elements[i]
                        text = text.strip()
                        # 場所 (svg path d="M12 14....")
                        if await elem.locator('svg path[d^="M12 14"]').count() > 0 and text: location = text; continue
                        # ウェブサイト (svg path d="M18.36 5.64....") - aタグからhrefを取得
                        if await elem.locator('svg path[d^="M18.36"]').count() > 0:
                             link_elem = elem.locator('a').first
                             if await link_elem.count() > 0: website = await link_elem.get_attribute('href') or text # hrefがなければテキスト
                             else: website = text
                             continue
                        # 参加日 (svg path d="M7 4....")
                        if await elem.locator('svg path[d^="M7 4"]').count() > 0 and text: join_date = text.replace("Joined ","").replace("に参加","").strip(); continue
                else:
                     self.logger.warning(f"プロフィールヘッダーアイテムが見つかりません ({profile_url})")

                profile_info["location"] = location.strip()
                profile_info["website"] = website.strip()
                profile_info["join_date"] = join_date.strip()
            except Exception as e_items: self.logger.warning(f"ヘッダーアイテム（場所/ウェブサイト/参加日）の抽出エラー ({profile_url}): {e_items}")


            # フォロー数、フォロワー数
            following_count = 0; followers_count = 0
            try:
                # フォロー/フォロワー数を含むリンク (href="/following", href="/followers") を探す
                 follow_links = await self.page.locator('a[href$="/following"], a[href$="/verified_followers"], a[href$="/followers"]').all()
                 for link_elem in follow_links:
                      href = await link_elem.get_attribute('href') or ""
                      # リンク内の数値 (span > span 構造が多い)
                      count_span = link_elem.locator('span > span').first
                      if await count_span.count() > 0:
                           count_text = await count_span.inner_text()
                           # "K" や "M" を考慮して数値に変換 (例: 1.2K -> 1200)
                           count_text = count_text.replace(',', '') # カンマ除去
                           multiplier = 1
                           if count_text.lower().endswith('k'): multiplier = 1000; count_text = count_text[:-1]
                           elif count_text.lower().endswith('m'): multiplier = 1000000; count_text = count_text[:-1]
                           try: count = int(float(count_text) * multiplier)
                           except ValueError: count = 0 # 変換失敗時は0

                           if "/following" in href: following_count = count
                           elif "/followers" in href: followers_count = count # verified_followers も followers として扱う
            except Exception as e_follow: self.logger.warning(f"フォロー/フォロワー数の抽出エラー ({profile_url}): {e_follow}")

            profile_info["following_count"] = following_count
            profile_info["followers_count"] = followers_count


            # ピン留めされたツイート (オプション)
            pinned_tweet_text = ""
            try:
                 pinned_container = self.page.locator('[data-testid="UserPinnedTweet"]').first
                 if await pinned_container.count() > 0:
                      pinned_text_locator = pinned_container.locator('[data-testid="tweetText"]').first
                      if await pinned_text_locator.count() > 0:
                           pinned_tweet_text = await pinned_text_locator.inner_text()
            except Exception as e_pinned: self.logger.warning(f"ピン留めツイートの抽出エラー ({profile_url}): {e_pinned}", exc_info=False)

            profile_info["pinned_tweet_text"] = pinned_tweet_text.strip()
            profile_info["scraped_timestamp"] = datetime.now().isoformat() # 収集時刻を追加

            # 収集した情報をキャッシュに保存
            self.cache.set(cache_key, profile_info)
            self.logger.info(f"プロフィール情報収集完了、キャッシュに保存: {user_handle or profile_url}")

            return profile_info

        except PlaywrightError as pe:
             if "close" in str(pe).lower(): self.logger.error(f"プロフィール収集中にページが予期せず閉じられました ({profile_url}): {pe}")
             else: self.logger.error(f"プロフィール収集中にPlaywrightエラー ({profile_url}): {pe}", exc_info=True)
             if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state(f"scrape_profile_playwright_error_{profile_url.split('/')[-1]}")
             return None
        except Exception as e:
             self.logger.error(f"プロフィール情報収集中に予期せぬエラー ({profile_url}): {e}", exc_info=True)
             if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state(f"scrape_profile_unexpected_error_{profile_url.split('/')[-1]}")
             return None


    async def validate_and_save_data(self, data: list | dict, filename_prefix: str) -> bool:
        """
        収集したプロフィールデータリストを検証し、JSONファイルとして保存する。

        Args:
            data (list | dict): 保存するデータ。通常はプロフィール情報のリスト。
            filename_prefix (str): ファイル名のプレフィックス (例: "list_members_12345")。

        Returns:
            bool: 保存が成功したかどうか。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prefix = "".join(x for x in filename_prefix if x.isalnum() or x in ['_', '-'])[:100]
        filename = os.path.join(self.raw_data_dir, f"{safe_prefix}_{timestamp}.json")

        if not data:
            self.logger.warning(f"保存するデータが空です: Prefix='{filename_prefix}'")
            return False # 空データは保存しない（または空ファイルを作成するか選択）

        # データ検証 (プロフィールリストの場合)
        if isinstance(data, list):
            if len(data) == 0:
                 self.logger.warning(f"保存データは空のリストです。Prefix='{filename_prefix}'")
                 # return False # 空リストは保存しない場合
            else:
                 required_keys = ["profile_url", "user_handle", "user_name"] # 最低限必要なキー
                 valid_items = 0
                 for item in data:
                      if isinstance(item, dict) and all(key in item for key in required_keys):
                           valid_items += 1
                      else:
                           # 不完全なデータをログに出力
                           self.logger.warning(f"リスト内に必須キーが不足している項目があります: {item.get('profile_url', 'URL不明')}, Keys={list(item.keys()) if isinstance(item, dict) else 'Not a dict'}")

                 if valid_items == 0:
                      self.logger.error(f"有効なプロフィールデータが1件も見つかりませんでした。保存を中止します。Prefix='{filename_prefix}'")
                      return False # 有効データがなければ保存しない
                 self.logger.info(f"データ検証: {valid_items}/{len(data)} 件の有効なプロフィールデータを確認。")
        elif not isinstance(data, dict): # リストでも辞書でもない場合
             self.logger.error(f"無効なデータ型です: {type(data)}。保存を中止します。Prefix='{filename_prefix}'")
             return False

        # ファイル保存処理 (playwright_scraper.py の save_data と同様)
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            file_size = os.path.getsize(filename)
            if file_size  dict | None:
        """
        設定に基づいてリスト収集タスクを実行するメインメソッド。

        Args:
            headless_mode (bool, optional): ブラウザをヘッドレスで実行するかどうか。Defaults to False.
            proxy (dict | None, optional): 使用するプロキシ設定。Defaults to None.

        Returns:
            dict | None: 各リストURLをキーとし、収集したプロフィール情報のリストを値とする辞書。エラー時はNone。
        """
        all_profiles_data = {}
        browser_initialized = False

        try:
            # --- 1. ブラウザ初期化 ---
            browser_initialized = await self.initialize_browser(headless=headless_mode, proxy_settings=proxy)
            if not browser_initialized:
                self.logger.error("ブラウザ初期化失敗。リスト収集処理を中止します。")
                return None

            # --- 2. ログイン ---
            login_success = await self.login_to_twitter()
            if not login_success:
                self.logger.error("ログイン失敗。リスト収集を続行できません。")
                if self.web_analyzer and self.page and not self.page.is_closed():
                     await self.web_analyzer.capture_page_state("list_collect_login_failed")
                return None

            self.logger.info("ログイン成功。リスト収集ターゲットの処理を開始します。")

            # --- 3. リストターゲット処理 ---
            list_targets = [t for t in self.scraping_targets if 'list_url' in t] # リストURLを持つターゲットのみ抽出
            if not list_targets:
                 self.logger.warning("設定ファイルにリスト収集ターゲット ('list_url') が見つかりません。")
                 return {} # ターゲットがなければ空の結果を返す

            for i, target in enumerate(list_targets):
                 list_url = target['list_url']
                 max_members = target.get('max_members') # リストごとに最大メンバー数を指定可能に
                 self.logger.info(f"リストターゲット {i+1}/{len(list_targets)} 処理開始: URL='{list_url}', MaxMembers={max_members}")
                 if await self._check_page_closed(f"リスト {list_url} 処理開始"): break

                 list_profiles = []
                 try:
                     # メンバーURLリストを取得
                     member_urls = await self.collect_list_members(list_url, max_members=max_members)

                     if member_urls:
                         self.logger.info(f"{len(member_urls)} 件のメンバーURLからプロフィール情報収集を開始します。")
                         processed_count = 0
                         for j, member_url in enumerate(member_urls):
                             if await self._check_page_closed(f"プロフィール収集ループ ({j+1}/{len(member_urls)})"): break
                             self.logger.info(f"プロフィール収集中 ({j+1}/{len(member_urls)}): {member_url}")
                             profile_info = await self.scrape_profile_info(member_url)
                             if profile_info:
                                 list_profiles.append(profile_info)
                                 processed_count += 1

                             # プロフィール収集間の待機 (重要: レート制限回避)
                             wait_time = random.uniform(1.5, 3.5) # 1.5秒から3.5秒のランダム待機
                             self.logger.debug(f"次のプロフィール収集まで {wait_time:.1f} 秒待機...")
                             await asyncio.sleep(wait_time)

                             # 定期的に進捗ログを表示 (例: 10件ごと)
                             if (j + 1) % 10 == 0:
                                  self.logger.info(f"進捗: {j+1}/{len(member_urls)} 件のプロフィールURLを処理済み。")


                         self.logger.info(f"リスト '{list_url}' のプロフィール収集完了。{processed_count} 件成功。")
                         if list_profiles:
                             # 収集したプロフィールデータを保存
                             list_id = list_url.split('/')[-1]
                             save_success = await self.validate_and_save_data(list_profiles, f"list_members_{list_id}")
                             if save_success:
                                 all_profiles_data[list_url] = {"status": "success", "count": len(list_profiles)}
                             else:
                                  all_profiles_data[list_url] = {"status": "save_failed", "count": len(list_profiles)}
                         else: # プロフィール収集が0件だった場合
                              all_profiles_data[list_url] = {"status": "no_profiles_collected", "count": 0}

                     else:
                         self.logger.warning(f"リスト '{list_url}' からメンバーURLが取得できませんでした。")
                         all_profiles_data[list_url] = {"status": "no_member_urls", "count": 0}

                 except Exception as e_list_proc:
                      self.logger.error(f"リスト '{list_url}' の処理中に予期せぬエラー: {e_list_proc}", exc_info=True)
                      all_profiles_data[list_url] = {"status": "processing_error"}
                      # エラーが発生しても次のリストへ進む

                 # リスト間のインターバル
                 if i  dict:
        """現在のページのウェブ構造を分析する"""
        if await self._check_page_closed("構造分析"): return {"error": "Page is closed"}
        if self.web_analyzer: return await self.web_analyzer.analyze_web_structure()
        else: self.logger.warning("WebStructureAnalyzer未初期化"); return {"error": "Analyzer not initialized"}


# --- 実行ブロック ---
if __name__ == "__main__":
    import random # ランダム待機用

    # --- ロガー設定 ---
    log_filename = "twitter_list_collector_main.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[ logging.FileHandler(log_filename, encoding='utf-8'), logging.StreamHandler() ]
    )
    main_logger = logging.getLogger("ListCollectorMain")

    # --- 設定 ---
    config_manager = ConfigManager() # 仮のConfigManagerを使用

    # --- コレクターインスタンス生成 ---
    collector = TwitterListInfoCollector(config_manager, logger=main_logger)

    # --- 非同期処理実行 ---
    try:
        main_logger.info("リスト収集処理を開始します...")
        asyncio.run(collector.main(run_headless=False, use_proxy=None))
        main_logger.info("リスト収集処理が終了しました。")
    except KeyboardInterrupt:
        main_logger.info("\n処理がユーザーによって中断されました。")
    except Exception as e:
        main_logger.error(f"メイン実行ブロックで未捕捉のエラーが発生しました: {e}", exc_info=True)

```

Citations:
[1] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/05c38884-c754-427f-96ab-c33121b8286b/playwright_scraper.py
[2] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/ee63d7f8-ff93-4cbf-8f5d-62a1f2433d59/paste-2.txt
[3] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/170acb19-5950-4489-a05a-3b72c4b9f942/list_collector.py
[4] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/141d32c0-5733-43ae-b377-2fb9527e961e/playwright_scraper.py
[5] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/409fb2e8-9311-49f5-9625-2deec2ab94aa/web_structure_analyzer.py
[6] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/503f1a6d-298a-4bcf-8c60-14018af7e65c/adaptive_selectors.py
[7] https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/52522745/1c5abfe0-5fc4-4113-8caf-2fce15fb8bc2/configuration_manager.py

---
Perplexity の Eliot より: pplx.ai/share