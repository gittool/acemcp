"""Global logging configuration for acemcp.

このモジュールは、acemcpプロジェクト全体のログ設定を管理します。
センシティブ情報のマスキング、ログレベルの制御、ファイルローテーションなどの
機能を提供します。
"""

import os
from pathlib import Path

from loguru import logger

from acemcp.utils import mask_sensitive_data

# Flag to track if logging has been configured
_logging_configured = False
# Store handler IDs to avoid removing them
_console_handler_id: int | None = None
_file_handler_id: int | None = None


def sanitize_log_message(record: dict) -> bool:
    """ログメッセージからセンシティブ情報をマスキングします。

    このフィルターは、ログメッセージ内のトークン、パスワード、APIキーなどの
    センシティブ情報を検出し、マスキングします。

    Args:
        record: Loguruのログレコード

    Returns:
        bool: 常にTrue（ログメッセージは常に処理される）
    """
    # メッセージをマスキング
    record["message"] = mask_sensitive_data(record["message"])
    return True


def setup_logging() -> None:
    """Setup global logging configuration with file rotation.

    Configures loguru to write logs to ~/.acemcp/log/acemcp.log with:
    - Maximum file size: 5MB
    - Maximum number of files: 10 (rotation)
    - Log format with timestamp, level, and message
    - Sensitive information masking (tokens, passwords, API keys)
    - Configurable log level via ACEMCP_LOG_LEVEL environment variable

    This function can be called multiple times safely - it will only configure once.
    Note: This function preserves any existing handlers (e.g., WebSocket log broadcaster).

    Environment Variables:
        ACEMCP_LOG_LEVEL: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
                         デフォルトはINFO

    Raises:
        OSError: ログディレクトリの作成に失敗した場合
    """
    global _logging_configured, _console_handler_id, _file_handler_id  # noqa: PLW0603

    if _logging_configured:
        return

    # Define log directory and file
    log_dir = Path.home() / ".acemcp" / "log"
    log_file = log_dir / "acemcp.log"

    # Create log directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # フォールバック: カレントディレクトリに作成
        logger.warning(
            f"Failed to create log directory at {log_dir}: {e}. "
            f"Falling back to current directory."
        )
        log_dir = Path.cwd() / "log"
        log_file = log_dir / "acemcp.log"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e2:
            logger.error(f"Failed to create fallback log directory: {e2}")
            raise

    # Remove only the default handler (handler_id=0) to avoid duplicate logs
    # This preserves any custom handlers like the WebSocket broadcaster
    try:
        logger.remove(0)
    except ValueError:
        # Handler 0 might already be removed, that's fine
        pass

    # 環境変数からログレベルを取得（デフォルト: INFO）
    console_log_level = os.getenv("ACEMCP_LOG_LEVEL", "INFO").upper()

    # Add console handler with configurable level and sensitive info filtering
    _console_handler_id = logger.add(
        sink=lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=console_log_level,
        colorize=True,
        filter=sanitize_log_message,
    )

    # Add file handler with rotation and detailed format
    _file_handler_id = logger.add(
        sink=str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {process} | {thread.name} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="5 MB",  # Rotate when file reaches 5MB
        retention=10,      # Keep at most 10 files
        compression="zip", # Compress rotated files
        encoding="utf-8",
        enqueue=True,      # Thread-safe logging
        filter=sanitize_log_message,
    )

    _logging_configured = True
    logger.info(f"Logging configured: log file at {log_file}, console level: {console_log_level}")

