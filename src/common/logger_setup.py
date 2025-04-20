# src/common/logger_setup.py (推奨される実装例)

import logging
import logging.handlers
import sys
import os
from logging import Logger, Formatter, StreamHandler, Handler # 必要なクラスをインポート
from logging.handlers import RotatingFileHandler

# 定数
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILENAME = "application.log"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5

def setup_logger(
    log_name: str | None = None, # ルートロガーを取得する場合は None
    log_level: int | str = DEFAULT_LOG_LEVEL,
    log_dir: str = DEFAULT_LOG_DIR,
    log_filename: str = DEFAULT_LOG_FILENAME,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    log_to_console: bool = True,
    log_to_file: bool = True,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    propagate: bool = True, # 上位ロガーへの伝播を制御
    disable_existing: bool = False # 既存ロガーの無効化フラグ
) -> Logger:
    """
    指定された設定でロガーをセットアップまたは取得します。

    Args:
        log_name (str | None): 設定するロガーの名前。Noneの場合はルートロガー。
        log_level (int | str): ログレベル (logging定数または'DEBUG', 'INFO'等の文字列)。
        log_dir (str): ログファイルを保存するディレクトリ。
        log_filename (str): ログファイル名。
        log_format (str): ログメッセージのフォーマット。
        date_format (str): ログメッセージの日時フォーマット。
        log_to_console (bool): Trueの場合、コンソール(stdout)にもログを出力します。
        log_to_file (bool): Trueの場合、指定されたファイルにログを出力します。
        max_bytes (int): ログファイルの最大サイズ (バイト単位)。ローテーション用。
        backup_count (int): 保持するバックアップログファイルの数。ローテーション用。
        propagate (bool): Trueの場合、ログメッセージを上位のロガーに伝播させます。
        disable_existing (bool): Trueの場合、既存のロガーを無効化します (通常はFalse推奨)。

    Returns:
        logging.Logger: 設定済みのロガーインスタンス。

    Raises:
        ValueError: 無効なログレベルが指定された場合。
        OSError: ログディレクトリの作成に失敗した場合。
    """
    # ロガーを取得
    logger: Logger = logging.getLogger(log_name)

    # ログレベルを設定
    numeric_level = logging.getLevelName(str(log_level).upper()) if isinstance(log_level, str) else log_level
    if not isinstance(numeric_level, int):
        # 無効なレベルが指定された場合はエラーを発生させるか、デフォルトにフォールバック
        # logging.warning(f"無効なログレベル指定: {log_level}。INFOレベルを使用します。")
        # numeric_level = logging.INFO
        raise ValueError(f"無効なログレベルが指定されました: {log_level}")

    logger.setLevel(numeric_level)

    # 既存のハンドラをクリアするかどうか (重複を避けるためクリア推奨)
    # ただし、他の場所で意図的にハンドラが追加されている場合は注意
    if logger.hasHandlers():
        logger.handlers.clear()

    # 上位ロガーへの伝播設定
    logger.propagate = propagate

    # disable_existing_loggers (logging.config系の機能に関連)
    # 通常、この関数内で直接制御するものではないが、引数として追加
    # logging.config.dictConfig({"disable_existing_loggers": disable_existing}) # 必要なら

    # フォーマッターを作成
    formatter = Formatter(log_format, datefmt=date_format)

    handlers: list[Handler] = []

    # ファイルハンドラー (ローテーション付き)
    if log_to_file:
        try:
            # ログディレクトリが存在しない場合は作成
            os.makedirs(log_dir, exist_ok=True)
            log_filepath = os.path.join(log_dir, log_filename)
            # RotatingFileHandlerを使用
            file_handler = RotatingFileHandler(
                log_filepath,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8' # エンコーディングを指定
            )
            file_handler.setLevel(numeric_level) # ハンドラーのレベルも設定
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except OSError as e:
            # ディレクトリ作成失敗時のエラーハンドリング
            logging.error(f"ログディレクトリの作成またはアクセスに失敗しました: {log_dir} - {e}", exc_info=True)
            # ここで例外を再発生させるか、処理を続行するか選択
            # raise
        except Exception as e:
            logging.error(f"ファイルハンドラーの設定中に予期せぬエラー: {e}", exc_info=True)

    # コンソールハンドラー
    if log_to_console:
        try:
            console_handler = StreamHandler(sys.stdout) # 標準出力へ
            console_handler.setLevel(numeric_level) # ハンドラーのレベルも設定
            console_handler.setFormatter(formatter)
            handlers.append(console_handler)
        except Exception as e:
            logging.error(f"コンソールハンドラーの設定中に予期せぬエラー: {e}", exc_info=True)

    # ハンドラが一つもない場合の警告 (またはNullHandlerの追加)
    if not handlers:
        logger.warning(f"ロガー '{log_name or 'root'}' にハンドラーが設定されていません。ログは出力されません。")
        # logging.NullHandler() を追加することも可能[8]
        # logger.addHandler(logging.NullHandler())
    else:
        # 作成したハンドラーをロガーに追加
        for handler in handlers:
            logger.addHandler(handler)

    # 設定完了のログメッセージ (INFOレベル以上で出力)
    if numeric_level <= logging.INFO:
        log_dest = []
        if log_to_file:
            log_dest.append(f"ファイル({os.path.join(log_dir, log_filename)})")
        if log_to_console:
            log_dest.append("コンソール")
        dest_str = " および ".join(log_dest) if log_dest else "（出力先なし）"
        logger.info(f"ロガー '{log_name or 'root'}' のセットアップ完了。出力先: {dest_str}。レベル: {logging.getLevelName(numeric_level)}")

    return logger

# --- 使用例 ---
if __name__ == "__main__":
    # メインアプリケーション用ロガーの設定
    app_logger = setup_logger(
        log_name="MyApplication",
        log_level="DEBUG", # 文字列で指定
        log_filename="my_app.log"
    )

    # モジュール用ロガーの取得 (通常は上位ロガーの設定を継承)
    module_logger = logging.getLogger("MyApplication.module")
    # モジュール固有の設定が必要な場合は再度 setup_logger を呼ぶことも可能だが、
    # 通常は getLogger で取得するだけで良い

    # ログ出力テスト
    app_logger.debug("アプリケーションのデバッグ情報")
    app_logger.info("アプリケーションが起動しました")
    module_logger.info("モジュール内の処理が開始されました")
    app_logger.warning("設定ファイルが見つかりません。デフォルト値を使用します。")
    try:
        1 / 0
    except ZeroDivisionError:
        app_logger.error("計算中にエラーが発生しました", exc_info=True) # exc_info=Trueでトレースバックを出力

    app_logger.critical("回復不能なエラー。アプリケーションを終了します。")

    # ルートロガーの設定例 (ライブラリ等が出力するログも拾う場合)
    # root_logger = setup_logger(log_name=None, log_level=logging.WARNING, log_filename="root.log")
