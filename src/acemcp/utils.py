"""共通ユーティリティ関数の定義。

このモジュールは、acemcpプロジェクト全体で使用される共通機能を提供します。
セキュリティ、バリデーション、エラーハンドリング、パフォーマンス最適化などの
機能が含まれます。
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

import httpx

from acemcp.constants import MAX_PATH_LENGTH, TOKEN_VISIBLE_CHARS

T = TypeVar("T")


def validate_path(
    path: str,
    must_exist: bool = True,
    must_be_absolute: bool = True,
) -> Path:
    """パスの安全性を検証し、正規化されたPathオブジェクトを返します。

    Args:
        path: 検証するパス文字列
        must_exist: パスが存在する必要があるか（デフォルト: True）
        must_be_absolute: パスが絶対パスである必要があるか（デフォルト: True）

    Returns:
        Path: 正規化され検証されたPathオブジェクト

    Raises:
        ValueError: パスが無効な場合（長すぎる、相対パス含む、存在しないなど）
        PermissionError: パスへのアクセス権限がない場合

    Examples:
        >>> validate_path("/home/user/project")
        PosixPath('/home/user/project')
        >>> validate_path("../secret")  # ValueError: パストラバーサル攻撃の可能性
    """
    if not path or not path.strip():
        msg = "パスが空です"
        raise ValueError(msg)

    if len(path) > MAX_PATH_LENGTH:
        msg = f"パスが長すぎます（最大{MAX_PATH_LENGTH}文字）: {len(path)}文字"
        raise ValueError(msg)

    # パストラバーサル攻撃の検出
    if ".." in path:
        msg = f"パストラバーサル攻撃の可能性があります: {path}"
        raise ValueError(msg)

    path_obj = Path(path)

    # 絶対パスチェック
    if must_be_absolute and not path_obj.is_absolute():
        msg = f"絶対パスが必要です: {path}"
        raise ValueError(msg)

    # シンボリックリンクの解決
    try:
        resolved_path = path_obj.resolve(strict=must_exist)
    except (OSError, RuntimeError) as e:
        msg = f"パスの解決に失敗しました: {path}"
        raise ValueError(msg) from e

    # 存在チェック
    if must_exist and not resolved_path.exists():
        msg = f"パスが存在しません: {path}"
        raise ValueError(msg)

    # 読み取り権限チェック
    if must_exist:
        try:
            # os.accessで基本的な読み取り権限を確認
            if not os.access(resolved_path, os.R_OK):
                msg = f"パスへのアクセス権限がありません: {path}"
                raise PermissionError(msg)

            # ディレクトリの場合はリスト可能かチェック
            if resolved_path.is_dir():
                list(resolved_path.iterdir())
            # ファイルの場合は最小限の読み取りテスト
            elif resolved_path.is_file():
                with open(resolved_path, 'rb') as f:
                    f.read(1)  # 1バイトのみ読み取り
        except PermissionError as e:
            msg = f"パスへのアクセス権限がありません: {path}"
            raise PermissionError(msg) from e

    return resolved_path


def mask_token(token: str, visible_chars: int = TOKEN_VISIBLE_CHARS) -> str:
    """トークンをマスキングします。

    Args:
        token: マスキングするトークン
        visible_chars: 先頭と末尾に表示する文字数（デフォルト: 4）

    Returns:
        str: マスキングされたトークン（例: "abcd****wxyz"）

    Examples:
        >>> mask_token("1234567890abcdef")
        '1234****cdef'
        >>> mask_token("short", visible_chars=2)
        'sh****rt'
    """
    if not token:
        return ""

    if len(token) <= visible_chars * 2:
        # トークンが短い場合は完全にマスキング
        return "*" * len(token)

    prefix = token[:visible_chars]
    suffix = token[-visible_chars:]
    return f"{prefix}****{suffix}"


def mask_sensitive_data(text: str) -> str:
    """テキスト内のセンシティブ情報をマスキングします。

    検出されるパターン:
    - Bearerトークン
    - APIキー
    - パスワード
    - 認証トークン

    Args:
        text: マスキングするテキスト

    Returns:
        str: センシティブ情報がマスキングされたテキスト

    Examples:
        >>> mask_sensitive_data("Authorization: Bearer abc123xyz")
        'Authorization: Bearer ****'
        >>> mask_sensitive_data("password=secret123")
        'password=****'
    """
    if not text:
        return text

    # Bearerトークンのマスキング
    text = re.sub(
        r"Bearer\s+[\w\-\.]+",
        "Bearer ****",
        text,
        flags=re.IGNORECASE,
    )

    # APIキーのマスキング
    text = re.sub(
        r"(api[_\-]?key|apikey)\s*[=:]\s*[\w\-\.]+",
        r"\1=****",
        text,
        flags=re.IGNORECASE,
    )

    # パスワードのマスキング
    text = re.sub(
        r"(password|passwd|pwd)\s*[=:]\s*\S+",
        r"\1=****",
        text,
        flags=re.IGNORECASE,
    )

    # トークンのマスキング
    text = re.sub(
        r"(token)\s*[=:]\s*[\w\-\.]+",
        r"\1=****",
        text,
        flags=re.IGNORECASE,
    )

    return text


def validate_url(url: str) -> bool:
    """URL形式を検証します。

    Args:
        url: 検証するURL

    Returns:
        bool: URLが有効な形式の場合True

    Examples:
        >>> validate_url("https://api.example.com/v1")
        True
        >>> validate_url("not-a-url")
        False
    """
    if not url:
        return False

    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:  # noqa: BLE001
        return False


def validate_file_extension(ext: str) -> bool:
    """ファイル拡張子の形式を検証します。

    Args:
        ext: 検証する拡張子

    Returns:
        bool: 拡張子が有効な形式の場合True（"."で始まる）

    Examples:
        >>> validate_file_extension(".py")
        True
        >>> validate_file_extension(".d.ts")
        True
        >>> validate_file_extension("py")
        False
    """
    if not ext:
        return False

    # "."で始まり、英数字に続いて._+-を許可する
    pattern = r"^\.[A-Za-z0-9][A-Za-z0-9._+-]*$"
    return bool(re.match(pattern, ext))


def validate_exclude_pattern(pattern: str) -> bool:
    """除外パターンの安全性を検証します。

    危険なパターン（システムディレクトリやルートを指すもの）を検出します。

    Args:
        pattern: 検証するパターン

    Returns:
        bool: パターンが安全な場合True

    Examples:
        >>> validate_exclude_pattern("*.log")
        True
        >>> validate_exclude_pattern("/etc/*")
        False
    """
    if not pattern:
        return False

    # 危険なパターンのリスト
    dangerous_patterns = [
        "/etc",
        "/sys",
        "/proc",
        "/dev",
        "/boot",
        "/root",
        "C:\\Windows",
        "C:\\System",
    ]

    # パターンが危険なディレクトリを含むかチェック
    for dangerous in dangerous_patterns:
        if pattern.startswith(dangerous):
            return False

    # パストラバーサルの検出
    if ".." in pattern:
        return False

    return True


def is_retryable_error(exception: Exception) -> bool:
    """例外がリトライ可能かどうかを判定します。

    Args:
        exception: 判定する例外

    Returns:
        bool: リトライ可能な場合True

    Examples:
        >>> is_retryable_error(httpx.TimeoutException())
        True
        >>> is_retryable_error(httpx.HTTPStatusError(..., response=Response(404)))
        False
    """
    # リトライ可能なhttpx例外
    retryable_httpx_errors = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.NetworkError,
    )

    if isinstance(exception, retryable_httpx_errors):
        return True

    # HTTPStatusErrorの場合、5xxエラーのみリトライ可能
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500

    return False


def format_error_message(exception: Exception, context: dict[str, Any]) -> str:
    """エラーメッセージをフォーマットします。

    Args:
        exception: フォーマットする例外
        context: エラーのコンテキスト情報

    Returns:
        str: フォーマットされたエラーメッセージ

    Examples:
        >>> format_error_message(
        ...     ValueError("Invalid path"),
        ...     {"operation": "validate", "path": "/tmp/test"}
        ... )
        'エラー: Invalid path | 操作: validate | パス: /tmp/test'
    """
    parts = [f"エラー: {exception!s}"]

    for key, value in context.items():
        if value is not None:
            parts.append(f"{key}: {value}")

    return " | ".join(parts)


async def async_batch_processor(
    items: list[T],
    batch_size: int,
    processor: Callable[[list[T]], Any],
    max_concurrent: int = 3,
) -> list[Any]:
    """アイテムのリストをバッチ処理し、並行実行します。

    Args:
        items: 処理するアイテムのリスト
        batch_size: バッチサイズ
        processor: バッチを処理する非同期関数
        max_concurrent: 最大同時実行数（デフォルト: 3）

    Returns:
        list: 処理結果のリスト

    Examples:
        >>> async def process_batch(batch):
        ...     return sum(batch)
        >>> await async_batch_processor([1, 2, 3, 4, 5], 2, process_batch, 2)
        [3, 7, 5]
    """
    if not items:
        return []

    # バッチに分割
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    # セマフォで同時実行数を制限
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_semaphore(batch: list[T]) -> Any:
        async with semaphore:
            return await processor(batch)

    # すべてのバッチを並行処理
    results = await asyncio.gather(
        *[process_with_semaphore(batch) for batch in batches],
        return_exceptions=True,
    )

    return results
