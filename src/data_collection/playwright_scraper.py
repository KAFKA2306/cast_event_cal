# src/data_collection/playwright_scraper.py

import random
import os
import time
import asyncio
import logging
import re
import json
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
    Page,
    BrowserContext,
    Browser
)

try:
    from src.common.web_structure_analyzer import WebStructureAnalyzer
    from src.common.adaptive_selectors import AdaptiveSelectors
    from src.common.configuration_manager import ConfigurationManager
    from src.common.simple_cache import SimpleCache
except ImportError:
    logging.warning("共通モジュールが見つかりません。ダミークラスを使用します。")
    class WebStructureAnalyzer:
        def __init__(self, page, logger, debug_dir): self.page = page; self.logger = logger; self.debug_dir=debug_dir
        async def capture_page_state(self, state_name): self.logger.info(f"仮: ページ状態キャプチャ ({state_name})")
        async def analyze_web_structure(self): self.logger.info("仮: 構造分析実行"); return {}

    class AdaptiveSelectors:
        def __init__(self, page, logger): self.page = page; self.logger = logger
        async def find_input_by_any_attribute(self, attributes: dict, timeout=10000):
            self.logger.info(f"仮: find_input_by_any_attribute ({attributes})")
            for attr, values in attributes.items():
                for value in values:
                    selector = f"input[{attr}='{value}']"
                    try:
                        element = self.page.locator(selector).first
                        is_visible = await element.is_visible(timeout=max(500, timeout // (len(attributes)*len(values) or 1)))
                        if is_visible: self.logger.info(f"仮: 要素発見 ({selector})"); return element
                    except Exception: pass
            self.logger.error("仮: 入力要素見つからず"); return None
        async def find_element_by_text_or_role(self, texts=None, role=None, data_testid=None, timeout=10000, exact_text=False):
            self.logger.info(f"仮: find_element_by_text_or_role (texts={texts}, role={role}, testid={data_testid})")
            locators_to_try = []
            if role and texts: locators_to_try.append(self.page.get_by_role(role, name=re.compile('|'.join(map(re.escape, texts)) if isinstance(texts, list) else re.escape(str(texts)), re.IGNORECASE), exact=exact_text))
            elif texts: locators_to_try.append(self.page.get_by_text(re.compile('|'.join(map(re.escape, texts)) if isinstance(texts, list) else re.escape(str(texts)), re.IGNORECASE), exact=exact_text))
            elif data_testid: locators_to_try.append(self.page.get_by_test_id(re.compile('|'.join(map(re.escape, data_testid)) if isinstance(data_testid, list) else re.escape(str(data_testid)), re.IGNORECASE)))
            elif role: locators_to_try.append(self.page.get_by_role(role))
            if not locators_to_try: return None
            try:
                locator = locators_to_try[0].first
                is_visible = await locator.is_visible(timeout=timeout)
                if is_visible: self.logger.info(f"仮: 要素発見 (最初の候補)"); return locator
            except Exception: pass
            self.logger.error("仮: 要素見つからず"); return None

    class SimpleCache:
        def __init__(self, cache_dir='cache', logger=None): self.cache_dir=cache_dir; self.logger=logger or logging.getLogger(__name__); os.makedirs(cache_dir, exist_ok=True)
        def get(self, key): self.logger.info(f"仮: キャッシュ取得 ({key})"); return None
        def set(self, key, data): self.logger.info(f"仮: キャッシュ設定 ({key})")

    class ConfigurationManager:
        def __init__(self, config_path=None): self.config = self._load_dummy_config()
        def get_config(self): return self.config
        def _load_dummy_config(self):
            return {
                'raw_data_dir': 'data/raw_scraped_data/',
                'debug_data_dir': 'data/debug_data/',
                'cache_dir': 'cache',
                'scraping_targets': [
                    {'query': 'lang:ja (イベント OR 開催 OR 主催 OR join OR ジョイン OR リクイン OR reqin OR リクエストインバイト OR "request invite" OR 本日 OR 営業 OR 応募) (VRChat OR VRC) min_retweets:3'},
                    {'list_url': 'https://x.com/i/lists/1834685283276935624'}
                ],
                'twitter_credentials': {
                    'username': os.environ.get("TWITTER_USERNAME"),
                    'password': os.environ.get("TWITTER_PASSWORD")
                }
            }

class EnhancedTwitterScraper:
    """
    Playwrightを使用してTwitter (X) から情報をスクレイピングするクラス。
    ログイン、ツイート検索、データ保存などの機能を持つ。
    """
    def __init__(self, config_manager: ConfigurationManager, logger: logging.Logger | None = None):
        """
        EnhancedTwitterScraperを初期化する。
        Args:
            config_manager (ConfigurationManager): 設定管理オブジェクト。
            logger (logging.Logger | None, optional): ログ出力用のロガー。 Defaults to None (新規作成).
        """
        self.config_manager = config_manager

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

        config = self.config_manager.get_config()
        self.scraping_targets = config.get('scraping_targets', [])
        self.raw_data_dir = config.get('raw_data_dir', 'data/raw_scraped_data/')
        self.debug_data_dir = config.get('debug_data_dir', 'data/debug_data/')
        self.cache_dir = config.get('cache_dir', 'cache')

        for directory in [self.raw_data_dir, self.debug_data_dir, self.cache_dir]:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                self.logger.error(f"ディレクトリ作成失敗: {directory}, エラー: {e}")

        #self.cache = SimpleCache(cache_dir=self.cache_dir, logger=self.logger)

        self.playwright: async_playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        self.web_analyzer: WebStructureAnalyzer | None = None
        self.adaptive_selectors: AdaptiveSelectors | None = None

    async def initialize_browser(self, headless: bool = False, proxy_settings: dict | None = None) -> bool:
        """ Playwrightブラウザを初期化 """
        try:
            self.logger.info(f"Playwright ブラウザ初期化開始 (Headless: {headless})")
            self.playwright = await async_playwright().start()

            browser_launch_options = {
                'headless': headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--start-maximized',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--disable-plugins-discovery',
                    '--disable-infobars',
                ]
            }
            if proxy_settings:
                browser_launch_options['proxy'] = proxy_settings
                self.logger.info(f"プロキシ設定を使用: {proxy_settings.get('server')}")

            self.browser = await self.playwright.chromium.launch(**browser_launch_options)
            self.logger.info("Chromium ブラウザを起動しました。")

            context_options = {
                'user_agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                'viewport': {"width": 1920, "height": 1080},
                'locale': "ja-JP",
                'timezone_id': "Asia/Tokyo",
                'geolocation': {"latitude": 35.6895, "longitude": 139.6917},
                'permissions': ["geolocation"],
                'color_scheme': "no-preference",
                'device_scale_factor': 1.0,
            }
            self.context = await self.browser.new_context(**context_options)
            self.logger.info("ブラウザコンテキストを作成しました。")

            await self.context.add_init_script("""
                if (navigator.webdriver) { Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); }
                if (window.navigator.chrome) { window.navigator.chrome = { runtime: {} }; }
                if (window.chrome) { window.chrome = { app: { isInstalled: false }, runtime: {} }; }
                if (Notification && Notification.permission) { const op = Notification.permission; Object.defineProperty(Notification, 'permission', { get: () => op === 'denied' ? 'denied' : 'default', configurable: true }); }
                try { Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en-US', 'en'], configurable: true }); } catch (e) { console.warn('Failed to modify navigator.languages:', e); }
            """)
            self.logger.info("検出対策用の init スクリプトを追加しました。")

            self.page = await self.context.new_page()
            self.logger.info("新しいページを作成しました。")

            self.web_analyzer = WebStructureAnalyzer(self.page, self.logger, self.debug_data_dir)
            self.adaptive_selectors = AdaptiveSelectors(self.page, self.logger)

            self.logger.info("ブラウザとページの初期化が完了しました。")
            return True

        except PlaywrightError as pe:
            self.logger.error(f"Playwright関連のエラーによりブラウザ初期化失敗: {pe}", exc_info=True)
            await self.close_browser()
            return False
        except Exception as e:
            self.logger.error(f"予期せぬエラーによりブラウザ初期化失敗: {e}", exc_info=True)
            await self.close_browser()
            return False

    async def close_browser(self):
        """ Playwright関連のリソースを安全に閉じる """
        self.logger.info("ブラウザ関連リソースのクローズ処理を開始します。")
        if hasattr(self, 'page') and self.page and not self.page.is_closed():
            try: await self.page.close(); self.logger.info("ページを閉じました。")
            except Exception as e: self.logger.error(f"ページのクローズ中にエラー: {e}")
            self.page = None
        if hasattr(self, 'context') and self.context:
             try: await self.context.close(); self.logger.info("コンテキストを閉じました。")
             except Exception as e:
                 if "context closed" not in str(e).lower(): self.logger.error(f"コンテキストのクローズ中にエラー: {e}")
                 else: self.logger.debug(f"コンテキストは既に閉じられていたか、クローズ中に軽微なエラー: {e}")
             self.context = None
        if hasattr(self, 'browser') and self.browser and self.browser.is_connected():
            try: await self.browser.close(); self.logger.info("ブラウザを閉じました。")
            except Exception as e: self.logger.error(f"ブラウザのクローズ中にエラー: {e}")
            self.browser = None
        if hasattr(self, 'playwright') and self.playwright:
            try: await self.playwright.stop(); self.logger.info("Playwrightプロセスを停止しました。")
            except Exception as e: self.logger.error(f"Playwrightプロセスの停止中にエラー: {e}")
            self.playwright = None
        self.logger.info("ブラウザ関連リソースのクローズ処理が完了しました。")

    async def _check_page_closed(self, operation_name: str) -> bool:
        """ ページが閉じられていないか確認 """
        if not self.page or self.page.is_closed():
            self.logger.error(f"{operation_name} を実行できません: ページが閉じられています。")
            return True
        return False

    async def login_to_twitter(self) -> bool:
        """ Twitter (X) にログインする """
        if await self._check_page_closed("Twitterログイン"): return False
        assert self.page is not None and self.adaptive_selectors is not None and self.web_analyzer is not None

        self.logger.info("Twitter ログインプロセス開始")

        config = self.config_manager.get_config()
        credentials = config.get('twitter_credentials', {})
        username = credentials.get('username') or os.environ.get("TWITTER_USERNAME")
        password = credentials.get('password') or os.environ.get("TWITTER_PASSWORD")

        if not username or not password:
             self.logger.info("環境変数/設定ファイルに認証情報が見つからないため、keyring を試します。")
             try:
                 import keyring
                 username = keyring.get_password("twitter", "username")
                 password = keyring.get_password("twitter", "password")
                 if username and password: self.logger.info("keyring から認証情報を取得しました。")
                 else: self.logger.info("keyring に認証情報が見つかりませんでした。")
             except Exception as e:
                 self.logger.warning(f"keyring 読み込みエラー: {e}")

        if not username or not password:
            self.logger.info("認証情報が見つからないため、ユーザー入力を求めます。")
            try:
                if os.isatty(0):
                    print("--------------------------------------------------")
                    print("Twitter (X) の認証情報が必要です。")
                    username = input("ユーザー名またはメールアドレス: ")
                    import getpass
                    password = getpass.getpass("パスワード: ")
                    print("--------------------------------------------------")
                else:
                    self.logger.error("非インタラクティブ環境のため、ユーザー入力はスキップされました。認証情報が必要です。")
                    return False
            except EOFError:
                self.logger.error("ユーザー入力の取得中にEOFError。非インタラクティブ環境では実行できません。")
                return False
            except Exception as e:
                self.logger.error(f"ユーザー入力の取得中にエラー: {e}")
                return False

        if not username or not password:
            self.logger.error("Twitter のユーザー名またはパスワードが取得できませんでした。")
            return False

        self.logger.info(f"使用するユーザー名: {username}")
        self.logger.info(f"使用するパスワード: {'*' * len(password)}")

        try:
            login_url = "https://twitter.com/login"
            self.logger.info(f"ログインページに移動します: {login_url}")
            if await self._check_page_closed("ログインページへの移動"): return False
            await self.page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            self.logger.info("ページ遷移完了、要素待機開始")

            try:
                 if await self._check_page_closed("ユーザー名フィールド待機"): return False
                 username_selector = 'input[name="text"], input[autocomplete="username"], input[aria-label*="ユーザー名"], input[aria-label*="username"]'
                 await self.page.wait_for_selector(username_selector, timeout=30000)
                 self.logger.info("ログインページの主要入力フィールドを検出")
            except PlaywrightTimeoutError as e:
                 self.logger.error(f"ログインページの主要入力フィールド待機中にタイムアウト: {e}")
                 await self.web_analyzer.capture_page_state("login_page_load_fail_or_changed")
                 return False

            self.logger.info("ユーザー名入力フィールドを検索・入力します")
            if await self._check_page_closed("ユーザー名入力"): return False
            username_input = await self.adaptive_selectors.find_input_by_any_attribute(
                attributes={
                    'name': ['text'],
                    'autocomplete': ['username'],
                    'aria-label': ['電話番号、メールアドレス、またはユーザー名', 'Phone, email address, or username', '電話番号またはメールアドレス', 'Phone or email address', 'ユーザー名', 'Username'],
                    'type': ['text', 'email']
                },
                timeout=15000
            )
            if not username_input:
                self.logger.error("ユーザー名入力フィールドが見つかりませんでした。")
                await self.web_analyzer.capture_page_state("username_input_missing")
                return False
            await username_input.fill(username)
            await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))

            self.logger.info("「次へ」ボタンを検索・クリックします")
            next_button_locator = self.page.get_by_role('button', name=re.compile(r'次へ|Next', re.IGNORECASE)) \
                                        .or_(self.page.locator('[data-testid="ocfEnterTextNextButton"]')) \
                                        .or_(self.page.locator('[data-testid="next_link"]')) \
                                        .or_(self.page.get_by_role('button', name=re.compile(r'Allow|許可', re.IGNORECASE)))

            if not await self._click_element(next_button_locator, "「次へ」ボタン", "next_button_missing_v2", "next_button_click_error_v2"):
                return False

            password_input = None
            additional_input_handled = False

            self.logger.info("パスワード、追加認証、または2FAフィールドを待機しています...")
            if await self._check_page_closed("パスワード/追加認証/2FA待機"): return False
            password_selector = 'input[name="password"], input[autocomplete="current-password"]'
            additional_selector = 'input[data-testid="ocfEnterTextTextInput"], input[name="text"][aria-label*="ユーザー名"], input[name="challenge_response"]'
            two_fa_selector = 'input[name="challenge_response"][aria-label*="認証コード"], input[data-testid*="LoginVerificationCode"]'
            combined_selector = f"{password_selector}, {additional_selector}, {two_fa_selector}"

            try:
                await self.page.wait_for_selector(combined_selector, timeout=20000)

                self.logger.info("パスワード、追加認証、または2FAフィールドのいずれかを検出しました。")

                password_input_element = self.page.locator(password_selector).first
                additional_input_element = self.page.locator(additional_selector).first
                two_fa_input_element = self.page.locator(two_fa_selector).first

                if await password_input_element.is_visible(timeout=1000):
                    self.logger.info("パスワード入力フィールドを検出しました。")
                    password_input = password_input_element
                elif await additional_input_element.is_visible(timeout=1000):
                    self.logger.warning("追加認証（電話番号/ユーザー名）が求められました。ユーザー名を入力します。")
                    if await self._check_page_closed("追加認証入力"): return False
                    await additional_input_element.fill(username)
                    additional_input_handled = True
                    await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))

                    self.logger.info("追加認証画面の「次へ」ボタンを検索・クリックします。")
                    if await self._check_page_closed("追加認証「次へ」ボタン検索"): return False
                    next_button_again_locator = self.page.get_by_role('button', name=re.compile(r'次へ|Next', re.IGNORECASE)) \
                                                     .or_(self.page.locator('[data-testid="ocfEnterTextNextButton"]'))
                    try:
                        next_button_again = next_button_again_locator.first
                        await next_button_again.wait_for(state='visible', timeout=10000)
                        await next_button_again.click()
                        self.logger.info("追加認証画面の「次へ」ボタンをクリックしました。")
                        await asyncio.sleep(1.5 + random.uniform(0.2, 0.8))
                        self.logger.info("追加認証後、パスワード入力フィールドを再検索します。")
                        if await self._check_page_closed("追加認証後パスワード検索"): return False
                        await self.page.wait_for_selector(password_selector, timeout=15000)
                        password_input = self.page.locator(password_selector).first
                        if not await password_input.is_visible(timeout=1000):
                             self.logger.error("追加認証後のパスワード入力フィールドが見つかりません。")
                             await self.web_analyzer.capture_page_state("password_input_missing_after_challenge_v2")
                             return False
                        self.logger.info("追加認証後、パスワード入力フィールドを検出しました。")
                    except PlaywrightTimeoutError:
                        self.logger.error("追加認証画面の「次へ」ボタン or パスワードフィールド(再) が見つかりません。")
                        await self.web_analyzer.capture_page_state("next_button_or_password_missing_after_challenge")
                        return False
                    except Exception as e:
                         self.logger.error(f"追加認証の「次へ」/パスワード再検索クリック中にエラー: {e}")
                         await self.web_analyzer.capture_page_state("next_button_click_error_after_challenge")
                         return False

                elif await two_fa_input_element.is_visible(timeout=1000):
                    self.logger.info("2FAコード入力フィールドを検出しました。")
                    if await self.handle_2fa(two_fa_input_element):
                        self.logger.info("2FA処理が成功しました。ログイン完了を確認します。")
                        password_input = None
                    else:
                        self.logger.error("2FA処理に失敗しました。")
                        return False
                else:
                     self.logger.error("パスワード/追加認証/2FAフィールドを検出しましたが、特定できませんでした。")
                     await self.web_analyzer.capture_page_state("unknown_login_step_field")
                     return False

            except PlaywrightTimeoutError:
                self.logger.error("パスワード、追加認証、または2FAフィールドの待機中にタイムアウトしました。")
                await self.web_analyzer.capture_page_state("password_challenge_2fa_timeout")
                return False

            if password_input and await password_input.is_visible():
                if await self._check_page_closed("パスワード入力"): return False
                self.logger.info("パスワードを入力します。")
                await password_input.fill(password)
                await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))

                self.logger.info("「ログイン」ボタンを検索・クリックします")
                login_button_locator = self.page.get_by_role('button', name=re.compile(r'ログイン|Log in', re.IGNORECASE)) \
                                            .or_(self.page.locator('[data-testid="ocfLoginButton"]')) \
                                            .or_(self.page.locator('[data-testid="LoginForm_Login_Button"]')) \
                                            .or_(self.page.locator('[data-testid="loginButton"]'))
                if not await self._click_element(login_button_locator, "「ログイン」ボタン", "login_button_missing_v2", "login_button_click_error_v2"):
                    return False

            elif password_input is None:
                self.logger.info("2FA処理後のため、「ログイン」ボタンクリックはスキップします。ログイン後の状態確認へ。")
                await asyncio.sleep(3 + random.uniform(0.5, 1.5))

            try:
                self.logger.info("ログイン成功を確認します（タイムライン要素が表示されるか）。")
                if await self._check_page_closed("ログイン成功確認"): return False
                timeline_selector = '[data-testid="primaryColumn"], [role="main"], nav[aria-label="メイン"]'
                await self.page.wait_for_selector(timeline_selector, timeout=25000)
                self.logger.info("ログイン成功を確認しました（タイムライン/ナビゲーション要素検出）。")
                return True
            except PlaywrightTimeoutError as e:
                self.logger.error(f"ログイン成功確認中にタイムアウトしました。ログイン失敗またはUI変更の可能性があります。: {e}")
                await self.web_analyzer.capture_page_state("login_verification_failed_v2")
                try:
                    error_message = await self.page.locator('[role="alert"], [data-testid*="error"]').first.text_content(timeout=1000)
                    if error_message:
                         self.logger.error(f"ログイン失敗メッセージ検出の可能性: {error_message[:100]}...")
                except:
                     pass
                return False

        except PlaywrightError as pe:
            error_msg = str(pe).lower()
            if "close" in error_msg or "disconnect" in error_msg or "target" in error_msg:
                self.logger.error(f"ログイン処理中にページや接続に関するPlaywrightエラー: {pe}")
            else:
                self.logger.error(f"ログインプロセスで予期せぬPlaywrightエラー: {pe}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed():
                await self.web_analyzer.capture_page_state("login_process_playwright_error_v2")
            return False
        except Exception as e:
            self.logger.error(f"ログインプロセス全体で予期せぬエラー: {e}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed():
                await self.web_analyzer.capture_page_state("login_process_unexpected_error_v2")
            return False
        finally:
            self.logger.info("Twitter ログインプロセス終了")

    async def handle_2fa(self, verification_input_element) -> bool:
        """ 2段階認証 (2FA) コード入力を処理 """
        if await self._check_page_closed("2FA処理"): return False
        assert self.page is not None and verification_input_element is not None

        self.logger.info("2段階認証 (2FA) の処理を開始します。")
        try:
            verification_code = ""
            if os.isatty(0):
                print("--------------------------------------------------")
                print("2段階認証コードが必要です。")
                verification_code = input("認証コードを入力してください: ")
                print("--------------------------------------------------")
            else:
                self.logger.error("非インタラクティブ環境のため、2FAコードを入力できません。")
                return False

            if not verification_code:
                self.logger.error("2FAコードが入力されませんでした。")
                return False

            if await self._check_page_closed("2FAコード入力"): return False
            await verification_input_element.fill(verification_code)
            await asyncio.sleep(0.5 + random.uniform(0.1, 0.3))

            if await self._check_page_closed("2FA確認ボタン検索"): return False
            confirm_button_locator = self.page.get_by_role('button', name=re.compile(r'次へ|Next|認証|Verify|確認', re.IGNORECASE)) \
                                         .or_(self.page.locator('[data-testid="ocfEnterTextNextButton"]')) \
                                         .or_(self.page.locator('[data-testid*="LoginVerificationCodeForm-submit"]'))
            try:
                confirm_button = confirm_button_locator.first
                await confirm_button.wait_for(state='visible', timeout=5000)
                await confirm_button.click()
                self.logger.info("2FAコードを送信しました。")
                await asyncio.sleep(2 + random.uniform(0.3, 0.7))
                return True
            except PlaywrightTimeoutError:
                self.logger.warning("2FAコード送信ボタンが見つかりませんでした。")
            if self.web_analyzer: await self.web_analyzer.capture_page_state("2fa_confirm_button_missing_v2")
            return False
        except Exception as e:
            self.logger.error(f"2FA確認ボタンのクリック中にエラー: {e}")
            if self.web_analyzer: await self.web_analyzer.capture_page_state("2fa_confirm_button_click_error")
            return False

        except EOFError:
            self.logger.error("2FAコードの入力が取得できませんでした (EOFError)。")
            return False
        except PlaywrightError as pe:
            self.logger.error(f"2FA処理中にPlaywrightエラー: {pe}", exc_info=("closed" not in str(pe).lower()))
            if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state("handle_2fa_playwright_error_v2")
            return False
        except Exception as e:
            self.logger.error(f"2FA処理中に予期せぬエラー: {e}", exc_info=True)
            if self.web_analyzer and self.page and not self.page.is_closed(): await self.web_analyzer.capture_page_state("handle_2fa_unexpected_error_v2")
            return False

    async def scrape_tweets(self, query: str, max_tweets: int | None = None) -> list[dict]:
        """ 指定されたクエリでツイートを検索し収集する """
        if await self._check_page_closed(f"ツイート収集開始 ({query})"): return []
        assert self.page is not None and self.web_analyzer is not None

        self.logger.info(f"ツイート検索とスクレイピングを開始: Query='{query}', MaxTweets={max_tweets}")
        tweets_data = []
        seen_tweet_ids = set()

        try:
            search_url = f"https://twitter.com/search?q={quote(query)}&src=typed_query&f=live"
            self.logger.info(f"検索URLに移動します: {search_url}")
            if await self._check_page_closed("検索URL移動"): return []
            try:
                await self.page.goto(search_url, wait_until="networkidle", timeout=60000)
                await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                self.logger.info("検索結果ページへの遷移と最初のツイート読み込みを確認しました。")
                await asyncio.sleep(2 + random.uniform(0.5, 1.0))
            except (PlaywrightTimeoutError, PlaywrightError) as nav_e:
                self.logger.error(f"検索URLへの遷移またはコンテンツ読み込みに失敗: {nav_e}")
                await self.web_analyzer.capture_page_state(f"search_goto_failed_{quote(query)[:50]}")
                self.logger.info("フォールバック: タイムライン上の検索バーからの検索を試みます。")
                if await self._check_page_closed("検索フォールバック(バー)"): return []
                try:
                    search_box_locator = self.page.get_by_test_id("SearchBox_Search_Input").or_(self.page.get_by_label(re.compile("検索|Search", re.I)))
                    search_box = search_box_locator.first
                    await search_box.wait_for(state="visible", timeout=15000)
                    await search_box.fill(query)
                    await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))
                    await search_box.press('Enter')
                    await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                    self.logger.info("フォールバック検索(バー)に成功しました。")
                    self.logger.info("スクレイピング処理は正常に完了しました。")
                except Exception as e:
                    self.logger.error(f"フォールバック検索中にエラーが発生しました: {e}")
            else:
                self.logger.error("スクレイピング処理が正常に完了しませんでした (結果がNone)。")

        except Exception as e:
            self.logger.error(f"ツイートスクレイピング中に予期しないエラーが発生しました: {e}", exc_info=True)
            if self.web_analyzer: await self.web_analyzer.capture_page_state("scrape_tweets_unexpected_error")
            return []

        return results

    async def analyze_web_structure(self) -> dict:
        """ 現在のページのウェブ構造を分析 """
        if await self._check_page_closed("構造分析"): return {"error": "Page is closed"}
        if self.web_analyzer:
            return await self.web_analyzer.analyze_structure()
        return {"warning": "WebStructureAnalyzerが初期化されていません。"}

    async def collect_list_members(self, list_url: str, max_members: int | None = None) -> list[dict]:
        """
        指定されたTwitterリストからメンバーを収集する。
        """
        if await self._check_page_closed(f"リストメンバー収集開始 ({list_url})"): return []
        assert self.page is not None and self.web_analyzer is not None

        members_data = []
        member_ids_seen = set()
        scroll_count = 0
        max_scrolls = 200  # スクロール回数の上限を設定 (無限スクロール対策)

        self.logger.info(f"リストメンバー収集開始: URL={list_url}, MaxMembers={max_members}")

        try:
            await self.page.goto(list_url, wait_until="networkidle", timeout=60000)
            self.logger.info(f"リストページに移動しました: {list_url}")

            # リストメンバーの初期ロードを待機
            await self.page.wait_for_selector('div[data-testid="UserCell"]', timeout=30000)
            self.logger.info("リストメンバーの初期ロード完了を確認")
            await asyncio.sleep(2 + random.uniform(0.5, 1.0))

            while True:
                if max_members and len(members_data) >= max_members:
                    self.logger.info(f"目標メンバー数 ({max_members}人) に達したため収集を終了します。")
                    break
                if scroll_count >= max_scrolls:
                    self.logger.warning(f"スクロール上限回数 ({max_scrolls}回) に達したため、メンバー収集を終了します。無限スクロールの可能性。")
                    break

                user_cells = await self.page.locator('div[data-testid="UserCell"]').all()
                if not user_cells:
                    self.logger.info("UserCell が見つかりません。リストの終端に達したか、構造が変更された可能性があります。")
                    break

                for cell in user_cells:
                    member_info = await self._extract_list_member_info(cell)
                    if member_info and member_info['user_id'] not in member_ids_seen:
                        members_data.append(member_info)
                        member_ids_seen.add(member_info['user_id'])
                        if max_members and len(members_data) >= max_members:
                            break
                if max_members and len(members_data) >= max_members:
                    break

                scroll_count += 1
                self.logger.info(f"ページをスクロールダウンします ({scroll_count} 回目)...")
                await self.page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
                await asyncio.sleep(1.5 + random.uniform(0.3, 0.7)) # スクロール後のロード待ち

                # 連続して新しいメンバーが読み込まれない場合、ループを終了する
                await asyncio.sleep(5)
                current_user_cells_count = len(await self.page.locator('div[data-testid="UserCell"]').all())
                if current_user_cells_count <= len(user_cells):
                    self.logger.info("新しいメンバーが読み込まれていないため、スクロールを停止します。")
                    break

            self.logger.info("リストメンバーのスクレイピングが完了しました。")
            return members_data

        except PlaywrightTimeoutError as timeout_err:
            self.logger.error(f"Playwrightタイムアウトエラーが発生しました: {timeout_err}")
            if "selector" in str(timeout_err):
                await self.web_analyzer.capture_page_state("collect_list_members_playwright_error")
            return []
        except PlaywrightError as playwright_err:
            self.logger.error(f"Playwrightエラーが発生しました: {playwright_err}")
            if "browser closed" not in str(playwright_err): # ブラウザが閉じたエラーは無視
                await self.web_analyzer.capture_page_state("collect_list_members_playwright_error")
            return []
        except Exception as e:
            self.logger.error(f"リストメンバー収集中に予期せぬエラーが発生しました: {e}", exc_info=True)
            await self.web_analyzer.capture_page_state("collect_list_members_unexpected_error")
            return []

        finally:
            self.logger.info("リストメンバー収集処理を終了します。")

    async def _extract_list_member_info(self, cell) -> dict | None:
        """
        UserCellからリストメンバーの情報を抽出する。
        """
        if await self._check_page_closed("リストメンバー情報抽出"): return None
        assert self.page is not None

        try:
            user_id_element = cell.locator('a[href^="/"]').first # ユーザーIDは通常、aタグのhref属性に含まれる
            user_id_href = await user_id_element.get_attribute('href')
            user_id = user_id_href.strip('/') if user_id_href else None
            if not user_id:
                self.logger.warning("ユーザーIDのhrefが見つかりませんでした。")
                return None

            name_locator = cell.locator('div[data-testid="User-Name"]').first
            names = await name_locator.locator('span').all_text_contents()
            user_name = names[0] if names else None
            display_name = names[1] if len(names) > 1 else None

            bio_locator = cell.locator('div[data-testid="UserCell-Text"]').first
            bio_text_element = bio_locator.locator('span').first
            bio = await bio_text_element.text_content() if bio_text_element else None

            is_verified_element = await cell.locator('svg[data-testid="icon-verified"]').count() > 0
            is_blue_verified_element = await cell.locator('svg[data-testid="icon-blue_checkmark"]').count() > 0
            is_verified = is_verified_element or is_blue_verified_element

            return {
                'user_id': user_id,
                'user_name': user_name,
                'display_name': display_name,
                'bio': bio,
                'is_verified': is_verified,
                'scraped_at': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"リストメンバー情報の抽出中にエラーが発生しました: {e}")
            return None
