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
                if remaining_timeout_ms <= 0:
                    self.logger.warning("全体タイムアウト。入力フィールド検索を中断します。")
                    return None

                # 現在の試行で使用するタイムアウト値（残り時間と試行あたり時間の小さい方）
                current_timeout_ms = max(min_time_per_attempt, min(time_per_attempt, remaining_timeout_ms))

                selector = f"input[{attr}='{value}']"
                self.logger.debug(f"入力セレクター試行: {selector} (Timeout: {current_timeout_ms:.0f}ms)")

                # ページが閉じられていないかチェック
                if self.page.is_closed():
                    self.logger.error("要素検索中にページが閉じられました。")
                    return None

                try:
                    element_locator = self.page.locator(selector)
                    # wait_for で要素がDOMに存在し、かつ可視状態になるのを待つ
                    await element_locator.first.wait_for(state="visible", timeout=current_timeout_ms)
                    self.logger.info(f"入力フィールド発見: {selector}")
                    return element_locator.first # 最初に見つかったものを返す
                except PlaywrightTimeoutError:
                    self.logger.debug(f"入力セレクター {selector} はタイムアウトしました。")
                except PlaywrightError as pe: # ページが閉じた場合など、より広範なPlaywrightエラー
                    if "closed" in str(pe).lower():
                        self.logger.error(f"要素検索中にページ/コンテキストが閉じられました ({selector}): {pe}")
                        return None # ページが閉じた場合は復旧不能なのでNoneを返す
                    else:
                        self.logger.error(f"入力セレクター {selector} の検索中にPlaywrightエラー: {pe}", exc_info=False)
                except Exception as e: # その他の予期せぬエラー
                    self.logger.error(f"入力セレクター {selector} の検索中に予期せぬエラー: {e}", exc_info=True) # 詳細ログ出力

        self.logger.error(f"指定されたどの属性でも入力フィールドが見つかりませんでした: {attributes}")
        return None

    async def find_element_by_text_or_role(
        self,
        texts: list[str] | str | None = None,
        role: str | None = None,
        data_testid: str | list[str] | None = None,
        timeout=10000,
        exact_text: bool = False
    ) -> Locator | None:
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
            if remaining_timeout_ms <= 0:
                self.logger.warning("全体タイムアウト。要素検索を中断します。")
                break

            current_timeout_ms = max(min_time_per_attempt, min(time_per_attempt, remaining_timeout_ms))
            description = locator_descriptions[i] # 現在の試行の説明を取得

            self.logger.info(f"要素試行 {i+1}/{attempts}: {description} (Timeout: {current_timeout_ms:.0f}ms)")

            # ページが閉じられていないかチェック
            if self.page.is_closed():
                self.logger.error("要素検索中にページが閉じられました。")
                return None

            try:
                locator = locator_func()
                # wait_for で要素がDOMに存在し、かつ可視状態になるのを待つ
                # first を使って、複数見つかった場合でも最初の一つを対象とする
                await locator.first.wait_for(state="visible", timeout=current_timeout_ms)

                # 要素が実際に見つかったか（可視になったか）を再確認 (countを使う)
                count = await locator.count()
                if count > 0:
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
                <html><body>
                    <h1>テストページ</h1>
                    <input name="username" placeholder="ユーザー名" />
                    <input type="password" data-testid="pwd-input" />
                    <button role="button">ログイン</button>
                    <button>キャンセル</button> <!-- Roleなし -->
                    <div data-testid="message-box">操作完了</div>
                    <a href="#">詳細はこちら</a>
                </body></html>
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
