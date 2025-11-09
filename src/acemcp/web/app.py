"""FastAPI web application for MCP server management."""

import asyncio
import json
import os
import time
import tomllib
from pathlib import Path
from typing import Any

import aiofiles
import tomli_w
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from acemcp.config import get_config
from acemcp.constants import (
    CONFIG_CACHE_TTL,
    DEFAULT_RATE_LIMIT,
    MAX_BATCH_SIZE,
    MAX_MAX_LINES_PER_BLOB,
    MAX_QUEUE_SIZE,
    MAX_WEBSOCKET_CLIENTS,
    MIN_BATCH_SIZE,
    MIN_MAX_LINES_PER_BLOB,
    STATUS_CACHE_TTL,
    WEBSOCKET_TIMEOUT,
)
from acemcp.utils import (
    format_error_message,
    validate_exclude_pattern,
    validate_file_extension,
    validate_url,
)
from acemcp.web.log_handler import get_log_broadcaster

# Initialize log broadcaster at module level to ensure single instance
log_broadcaster = get_log_broadcaster()

# 簡易キャッシュ
_config_cache: dict[str, Any] = {}
_status_cache: dict[str, Any] = {}


class ConfigUpdate(BaseModel):
    """Configuration update model with validation."""

    base_url: str | None = None
    token: str | None = None
    batch_size: int | None = None
    max_lines_per_blob: int | None = None
    text_extensions: list[str] | None = None
    exclude_patterns: list[str] | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """base_urlの検証。"""
        if v is not None and v:
            if not validate_url(v):
                msg = "base_url must be a valid HTTP/HTTPS URL"
                raise ValueError(msg)
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int | None) -> int | None:
        """batch_sizeの検証。"""
        if v is not None:
            if not MIN_BATCH_SIZE <= v <= MAX_BATCH_SIZE:
                msg = f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}"
                raise ValueError(msg)
        return v

    @field_validator("max_lines_per_blob")
    @classmethod
    def validate_max_lines(cls, v: int | None) -> int | None:
        """max_lines_per_blobの検証。"""
        if v is not None:
            if not MIN_MAX_LINES_PER_BLOB <= v <= MAX_MAX_LINES_PER_BLOB:
                msg = f"max_lines_per_blob must be between {MIN_MAX_LINES_PER_BLOB} and {MAX_MAX_LINES_PER_BLOB}"
                raise ValueError(msg)
        return v

    @field_validator("text_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str] | None) -> list[str] | None:
        """text_extensionsの検証。"""
        if v is not None:
            for ext in v:
                if not validate_file_extension(ext):
                    msg = f"Invalid file extension format (must start with '.'): {ext}"
                    raise ValueError(msg)
        return v

    @field_validator("exclude_patterns")
    @classmethod
    def validate_patterns(cls, v: list[str] | None) -> list[str] | None:
        """exclude_patternsの検証。"""
        if v is not None:
            for pattern in v:
                if not validate_exclude_pattern(pattern):
                    msg = f"Invalid or dangerous exclude pattern: {pattern}"
                    raise ValueError(msg)
        return v


class ToolRequest(BaseModel):
    """Tool execution request model."""

    tool_name: str
    arguments: dict


def create_app() -> FastAPI:
    """Create FastAPI application.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(title="Acemcp Management", description="MCP Server Management Interface", version="0.1.0")

    # レート制限の設定
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS設定（環境変数で制御）
    enable_cors = os.getenv("ACEMCP_ENABLE_CORS", "false").lower() == "true"
    if enable_cors:
        allowed_origins_str = os.getenv("ACEMCP_ALLOWED_ORIGINS", "*")
        allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info(f"CORS enabled with allowed origins: {allowed_origins}")

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        """Serve the main management page."""
        html_file = Path(__file__).parent / "templates" / "index.html"
        if html_file.exists():
            return html_file.read_text(encoding="utf-8")
        return "<h1>Acemcp Management</h1><p>Template not found</p>"

    @app.get("/api/config")
    @limiter.limit(DEFAULT_RATE_LIMIT)
    async def get_config_api(request: Request) -> dict[str, Any]:
        """Get current configuration.

        キャッシュを使用してパフォーマンスを向上させます。
        """
        # キャッシュをチェック
        cache_key = "config"
        if cache_key in _config_cache:
            cached_data, cached_time = _config_cache[cache_key]
            if time.time() - cached_time < CONFIG_CACHE_TTL:
                return cached_data

        config = get_config()
        response_data = {
            "index_storage_path": str(config.index_storage_path),
            "batch_size": config.batch_size,
            "max_lines_per_blob": config.max_lines_per_blob,
            "base_url": config.base_url,
            "token": config.get_masked_token(),  # マスキングされたトークンのみを返す
            "text_extensions": list(config.text_extensions),
            "exclude_patterns": config.exclude_patterns,
        }

        # キャッシュに保存
        _config_cache[cache_key] = (response_data, time.time())

        return {"status": "success", "data": response_data}

    @app.post("/api/config")
    @limiter.limit(DEFAULT_RATE_LIMIT)
    async def update_config_api(request: Request, config_update: ConfigUpdate) -> dict[str, str]:
        """Update configuration.

        Args:
            request: HTTP request
            config_update: Configuration updates

        Returns:
            Updated configuration

        Raises:
            HTTPException: 設定の更新に失敗した場合
        """
        try:
            from acemcp.config import USER_CONFIG_FILE

            if not USER_CONFIG_FILE.exists():
                return {
                    "error": {
                        "code": "CONFIG_NOT_FOUND",
                        "message": "User configuration file not found",
                        "details": {"file": str(USER_CONFIG_FILE)},
                    }
                }

            # ファイル読み込み（非同期）
            try:
                async with aiofiles.open(USER_CONFIG_FILE, "rb") as f:
                    content = await f.read()
                    settings_data = tomllib.loads(content.decode("utf-8"))
            except tomllib.TOMLDecodeError as e:
                error_msg = format_error_message(
                    e, {"operation": "load_config", "file": str(USER_CONFIG_FILE)}
                )
                logger.error(error_msg)
                return {
                    "error": {
                        "code": "CONFIG_CORRUPTED",
                        "message": "Configuration file is corrupted",
                        "details": {"file": str(USER_CONFIG_FILE), "error": str(e)},
                    }
                }
            except OSError as e:
                error_msg = format_error_message(
                    e, {"operation": "load_config", "file": str(USER_CONFIG_FILE)}
                )
                logger.error(error_msg)
                return {
                    "error": {
                        "code": "CONFIG_READ_ERROR",
                        "message": "Failed to read configuration file",
                        "details": {"file": str(USER_CONFIG_FILE), "error": str(e)},
                    }
                }

            # 設定の更新
            if config_update.base_url is not None:
                settings_data["BASE_URL"] = config_update.base_url
            if config_update.token is not None:
                settings_data["TOKEN"] = config_update.token
            if config_update.batch_size is not None:
                settings_data["BATCH_SIZE"] = config_update.batch_size
            if config_update.max_lines_per_blob is not None:
                settings_data["MAX_LINES_PER_BLOB"] = config_update.max_lines_per_blob
            if config_update.text_extensions is not None:
                settings_data["TEXT_EXTENSIONS"] = config_update.text_extensions
            if config_update.exclude_patterns is not None:
                settings_data["EXCLUDE_PATTERNS"] = config_update.exclude_patterns

            # ファイル書き込み（非同期）
            try:
                toml_bytes = tomli_w.dumps(settings_data).encode("utf-8")
                async with aiofiles.open(USER_CONFIG_FILE, "wb") as f:
                    await f.write(toml_bytes)
            except OSError as e:
                error_msg = format_error_message(
                    e, {"operation": "save_config", "file": str(USER_CONFIG_FILE)}
                )
                logger.error(error_msg)
                return {
                    "error": {
                        "code": "CONFIG_WRITE_ERROR",
                        "message": "Failed to write configuration file",
                        "details": {"file": str(USER_CONFIG_FILE), "error": str(e)},
                    }
                }

            # 設定のリロード
            config = get_config()
            config.reload()

            # キャッシュをクリア
            _config_cache.clear()

            logger.info("Configuration updated and reloaded successfully")
            return {
                "status": "success",
                "data": {"message": "Configuration updated and applied successfully!"},
            }

        except ValueError as e:
            # バリデーションエラー
            error_msg = format_error_message(e, {"operation": "validate_config"})
            logger.error(error_msg)
            return {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid configuration value",
                    "details": {"error": str(e)},
                }
            }
        except Exception as e:
            error_msg = format_error_message(e, {"operation": "update_config"})
            logger.error(error_msg)
            return {
                "error": {
                    "code": "UPDATE_ERROR",
                    "message": "Failed to update configuration",
                    "details": {"error": str(e)},
                }
            }

    @app.get("/api/status")
    @limiter.limit(DEFAULT_RATE_LIMIT)
    async def get_status(request: Request) -> dict[str, Any]:
        """Get server status.

        キャッシュを使用してパフォーマンスを向上させます。
        """
        # キャッシュをチェック
        cache_key = "status"
        if cache_key in _status_cache:
            cached_data, cached_time = _status_cache[cache_key]
            if time.time() - cached_time < STATUS_CACHE_TTL:
                return cached_data

        config = get_config()
        projects_file = config.index_storage_path / "projects.json"
        project_count = 0
        if projects_file.exists():
            try:
                with projects_file.open("r", encoding="utf-8") as f:
                    projects = json.load(f)
                    project_count = len(projects)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse projects file: {e}")
            except OSError as e:
                logger.error(f"Failed to read projects file: {e}")

        response_data = {
            "status": "running",
            "project_count": project_count,
            "storage_path": str(config.index_storage_path),
        }

        # キャッシュに保存
        _status_cache[cache_key] = (response_data, time.time())

        return {"status": "success", "data": response_data}

    @app.post("/api/tools/execute")
    @limiter.limit(DEFAULT_RATE_LIMIT)
    async def execute_tool(request: Request, tool_request: ToolRequest) -> dict[str, Any]:
        """Execute a tool for debugging.

        Args:
            request: HTTP request
            tool_request: Tool execution request

        Returns:
            Tool execution result
        """
        try:
            from acemcp.tools import search_context_tool

            tool_name = tool_request.tool_name
            arguments = tool_request.arguments

            logger.info(f"Executing tool: {tool_name}")

            if tool_name == "search_context":
                result = await search_context_tool(arguments)
            else:
                return {
                    "error": {
                        "code": "UNKNOWN_TOOL",
                        "message": f"Unknown tool: {tool_name}",
                        "details": {"tool": tool_name},
                    }
                }

            logger.info(f"Tool {tool_name} executed successfully")
            return {"status": "success", "data": result}

        except ValueError as e:
            error_msg = format_error_message(
                e, {"operation": "execute_tool", "tool": tool_request.tool_name}
            )
            logger.error(error_msg)
            return {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation error",
                    "details": {"tool": tool_request.tool_name, "error": str(e)},
                }
            }
        except FileNotFoundError as e:
            error_msg = format_error_message(
                e, {"operation": "execute_tool", "tool": tool_request.tool_name}
            )
            logger.error(error_msg)
            return {
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": "File not found",
                    "details": {"tool": tool_request.tool_name, "error": str(e)},
                }
            }
        except PermissionError as e:
            error_msg = format_error_message(
                e, {"operation": "execute_tool", "tool": tool_request.tool_name}
            )
            logger.error(error_msg)
            return {
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Permission denied",
                    "details": {"tool": tool_request.tool_name, "error": str(e)},
                }
            }
        except Exception as e:
            error_msg = format_error_message(
                e, {"operation": "execute_tool", "tool": tool_request.tool_name}
            )
            logger.error(error_msg)
            return {
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": "Tool execution failed",
                    "details": {"tool": tool_request.tool_name, "error": str(e)},
                }
            }

    @app.websocket("/ws/logs")
    async def websocket_logs(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time logs.

        クライアント数制限、キューサイズ制限、タイムアウト処理を実装しています。
        """
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

        try:
            # クライアント追加（制限チェック含む）
            await log_broadcaster.add_client(queue)
            logger.info("WebSocket client connected")

            last_message_time = time.time()

            while True:
                try:
                    # タイムアウト付きでメッセージを取得
                    log_message = await asyncio.wait_for(
                        queue.get(), timeout=WEBSOCKET_TIMEOUT
                    )
                    await websocket.send_text(log_message)
                    last_message_time = time.time()

                except asyncio.TimeoutError:
                    # タイムアウト: pingを送信して接続を確認
                    current_time = time.time()
                    if current_time - last_message_time > WEBSOCKET_TIMEOUT:
                        logger.info("WebSocket client timeout, closing connection")
                        break
                    # Pingメッセージを送信
                    await websocket.send_text(
                        json.dumps({"type": "ping", "timestamp": current_time})
                    )

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected normally")
        except RuntimeError as e:
            # クライアント数制限に達した場合
            logger.warning(f"WebSocket connection rejected: {e}")
            await websocket.close(code=1008, reason=str(e))
        except Exception as e:
            error_msg = format_error_message(e, {"operation": "websocket_logs"})
            logger.error(error_msg)
        finally:
            await log_broadcaster.remove_client(queue)
            logger.info("WebSocket client cleanup completed")

    return app

