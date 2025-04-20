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
