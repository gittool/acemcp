"""Configuration management for acemcp MCP server."""

import os
import stat
import toml
from pathlib import Path

from dynaconf import Dynaconf
from loguru import logger

from acemcp.constants import (
    CONFIG_FILE_MODE,
    MAX_BATCH_SIZE,
    MAX_MAX_LINES_PER_BLOB,
    MIN_BATCH_SIZE,
    MIN_MAX_LINES_PER_BLOB,
)
from acemcp.utils import mask_token, validate_exclude_pattern, validate_file_extension, validate_url

# Default configuration values
DEFAULT_CONFIG = {
    "BATCH_SIZE": 10,
    "MAX_LINES_PER_BLOB": 800,
    "MAX_CONCURRENT_UPLOADS": 3,
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 1.0,
    "BASE_URL": "https://api.example.com/v1",
    "TOKEN": "your-token-here-please-configure",
    "TEXT_EXTENSIONS": [
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".html",
        ".css",
        ".scss",
        ".sql",
        ".sh",
        ".bash",
    ],
    "EXCLUDE_PATTERNS": [
        ".venv",
        "venv",
        ".env",
        "env",
        "node_modules",
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        ".eggs",
        "*.egg-info",
        "dist",
        "build",
        ".idea",
        ".vscode",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".Python",
        "pip-log.txt",
        "pip-delete-this-directory.txt",
        ".coverage",
        "htmlcov",
        ".gradle",
        "target",
        "bin",
        "obj",
    ],
}

# User configuration and data paths
USER_CONFIG_DIR = Path.home() / ".acemcp"
USER_CONFIG_FILE = USER_CONFIG_DIR / "settings.toml"
USER_DATA_DIR = USER_CONFIG_DIR / "data"


def _ensure_user_config() -> Path:
    """Ensure user configuration file exists.

    Returns:
        Path to user configuration file

    Raises:
        OSError: 設定ディレクトリまたはファイルの作成に失敗した場合
    """
    try:
        if not USER_CONFIG_DIR.exists():
            USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created user config directory: {USER_CONFIG_DIR}")

        if not USER_DATA_DIR.exists():
            USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created user data directory: {USER_DATA_DIR}")

        if not USER_CONFIG_FILE.exists():
            with USER_CONFIG_FILE.open("w", encoding="utf-8") as f:
                toml.dump(DEFAULT_CONFIG, f)
            logger.info(f"Created default user config file: {USER_CONFIG_FILE}")

        # 設定ファイルの権限をチェックし、必要に応じて修正
        current_mode = os.stat(USER_CONFIG_FILE).st_mode
        if stat.S_IMODE(current_mode) != CONFIG_FILE_MODE:
            os.chmod(USER_CONFIG_FILE, CONFIG_FILE_MODE)
            logger.info(
                f"Set config file permissions to {oct(CONFIG_FILE_MODE)}: {USER_CONFIG_FILE}"
            )

    except OSError as e:
        logger.error(f"Failed to create or configure user config: {e}")
        raise

    return USER_CONFIG_FILE


# Ensure user config exists and initialize dynaconf
_ensure_user_config()

settings = Dynaconf(
    envvar_prefix="ACEMCP",
    settings_files=[str(USER_CONFIG_FILE)],
    load_dotenv=True,
    merge_enabled=True,
)


class Config:
    """MCP server configuration."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        """Initialize configuration.

        Args:
            base_url: Override BASE_URL from command line
            token: Override TOKEN from command line
        """
        self._cli_base_url: str | None = base_url
        self._cli_token: str | None = token

        self.index_storage_path: Path = USER_DATA_DIR
        self.batch_size: int = settings.get("BATCH_SIZE", DEFAULT_CONFIG["BATCH_SIZE"])
        self.max_lines_per_blob: int = settings.get("MAX_LINES_PER_BLOB", DEFAULT_CONFIG["MAX_LINES_PER_BLOB"])
        self.max_concurrent_uploads: int = settings.get("MAX_CONCURRENT_UPLOADS", DEFAULT_CONFIG["MAX_CONCURRENT_UPLOADS"])
        self.max_retries: int = settings.get("MAX_RETRIES", DEFAULT_CONFIG["MAX_RETRIES"])
        self.retry_delay: float = settings.get("RETRY_DELAY", DEFAULT_CONFIG["RETRY_DELAY"])
        self.base_url: str = base_url or settings.get("BASE_URL", DEFAULT_CONFIG["BASE_URL"])
        self.token: str = token or settings.get("TOKEN", DEFAULT_CONFIG["TOKEN"])
        self.text_extensions: set[str] = set(settings.get("TEXT_EXTENSIONS", DEFAULT_CONFIG["TEXT_EXTENSIONS"]))
        self.exclude_patterns: list[str] = settings.get("EXCLUDE_PATTERNS", DEFAULT_CONFIG["EXCLUDE_PATTERNS"])

    def reload(self) -> None:
        """Reload configuration from user config file, respecting CLI overrides."""
        settings.reload()

        self.index_storage_path = USER_DATA_DIR
        self.batch_size = settings.get("BATCH_SIZE", DEFAULT_CONFIG["BATCH_SIZE"])
        self.max_lines_per_blob = settings.get("MAX_LINES_PER_BLOB", DEFAULT_CONFIG["MAX_LINES_PER_BLOB"])
        self.max_concurrent_uploads = settings.get("MAX_CONCURRENT_UPLOADS", DEFAULT_CONFIG["MAX_CONCURRENT_UPLOADS"])
        self.max_retries = settings.get("MAX_RETRIES", DEFAULT_CONFIG["MAX_RETRIES"])
        self.retry_delay = settings.get("RETRY_DELAY", DEFAULT_CONFIG["RETRY_DELAY"])
        self.base_url = self._cli_base_url or settings.get("BASE_URL", DEFAULT_CONFIG["BASE_URL"])
        self.token = self._cli_token or settings.get("TOKEN", DEFAULT_CONFIG["TOKEN"])
        self.text_extensions = set(settings.get("TEXT_EXTENSIONS", DEFAULT_CONFIG["TEXT_EXTENSIONS"]))
        self.exclude_patterns = settings.get("EXCLUDE_PATTERNS", DEFAULT_CONFIG["EXCLUDE_PATTERNS"])

    def get_masked_token(self) -> str:
        """トークンをマスキングして返します。

        Returns:
            str: マスキングされたトークン（例: "abcd****wxyz"）
        """
        return mask_token(self.token)

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ValueError: 設定値が無効な場合
        """
        # base_urlの検証
        if not self.base_url:
            msg = "BASE_URL must be configured"
            raise ValueError(msg)
        if not validate_url(self.base_url):
            msg = f"BASE_URL must be a valid HTTP/HTTPS URL: {self.base_url}"
            raise ValueError(msg)

        # tokenの検証
        if not self.token:
            msg = "TOKEN must be configured"
            raise ValueError(msg)

        # batch_sizeの範囲検証
        if not MIN_BATCH_SIZE <= self.batch_size <= MAX_BATCH_SIZE:
            msg = f"BATCH_SIZE must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}, got {self.batch_size}"
            raise ValueError(msg)

        # max_lines_per_blobの範囲検証
        if not MIN_MAX_LINES_PER_BLOB <= self.max_lines_per_blob <= MAX_MAX_LINES_PER_BLOB:
            msg = f"MAX_LINES_PER_BLOB must be between {MIN_MAX_LINES_PER_BLOB} and {MAX_MAX_LINES_PER_BLOB}, got {self.max_lines_per_blob}"
            raise ValueError(msg)

        # max_concurrent_uploadsの範囲検証
        if not 1 <= self.max_concurrent_uploads <= 100:
            msg = f"MAX_CONCURRENT_UPLOADS must be between 1 and 100, got {self.max_concurrent_uploads}"
            raise ValueError(msg)

        # max_retriesの範囲検証
        if not 1 <= self.max_retries <= 10:
            msg = f"MAX_RETRIES must be between 1 and 10, got {self.max_retries}"
            raise ValueError(msg)

        # retry_delayの範囲検証
        if not 0.1 <= self.retry_delay <= 60.0:
            msg = f"RETRY_DELAY must be between 0.1 and 60.0 seconds, got {self.retry_delay}"
            raise ValueError(msg)

        # text_extensionsの形式検証
        for ext in self.text_extensions:
            if not validate_file_extension(ext):
                msg = f"Invalid file extension format (must start with '.'): {ext}"
                raise ValueError(msg)

        # exclude_patternsの安全性検証
        for pattern in self.exclude_patterns:
            if not validate_exclude_pattern(pattern):
                msg = f"Invalid or dangerous exclude pattern: {pattern}"
                raise ValueError(msg)


_config_instance: Config | None = None


def get_config() -> Config:
    """Get the global config instance.

    Returns:
        Config instance
    """
    global _config_instance  # noqa: PLW0603
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def init_config(base_url: str | None = None, token: str | None = None) -> Config:
    """Initialize config with command line arguments.

    Args:
        base_url: Override BASE_URL from command line
        token: Override TOKEN from command line

    Returns:
        Config instance
    """
    global _config_instance  # noqa: PLW0603
    _config_instance = Config(base_url=base_url, token=token)
    return _config_instance


config = get_config()

