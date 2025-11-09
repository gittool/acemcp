"""MCP server for codebase indexing."""

import argparse
import asyncio
import os
import signal
from typing import Any

import uvicorn
from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from acemcp.config import get_config, init_config
from acemcp.constants import MAX_PORT, MIN_PORT
from acemcp.logging_config import setup_logging
from acemcp.tools import search_context_tool
from acemcp.web import create_app

app = Server("acemcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools.

    Returns:
        List of available tools
    """
    return [
        Tool(
            name="search_context",
            description=(
                "Search for relevant code context based on a query within a specific project. "
                "This tool automatically performs incremental indexing before searching, ensuring "
                "results are always up-to-date. Returns formatted text snippets from the codebase "
                "that are semantically related to your query.\n\n"
                "IMPORTANT SECURITY NOTE:\n"
                "- Only use absolute paths that you trust\n"
                "- Avoid paths with '..' or suspicious patterns\n"
                "- The tool validates paths for security\n\n"
                "Use forward slashes (/) as path separators in project_root_path, even on Windows."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_root_path": {
                        "type": "string",
                        "description": "Absolute path to the project root directory. Use forward slashes (/) as separators. Example: C:/Users/username/projects/myproject",
                    },
                    "query": {
                        "type": "string",
                        "description": "Natural language search query to find relevant code context. This tool performs semantic search and returns code snippets that match your query. Examples: 'logging configuration setup initialization logger' (finds logging setup code), 'user authentication login' (finds auth-related code), 'database connection pool' (finds DB connection code), 'error handling exception' (finds error handling patterns), 'API endpoint routes' (finds API route definitions). The tool returns formatted text snippets with file paths and line numbers showing where the relevant code is located.",
                    },
                },
                "required": ["project_root_path", "query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> dict[str, Any]:
    """Handle tool calls.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool execution results
    """
    logger.info(f"Tool called: {name}")

    if name == "search_context":
        return await search_context_tool(arguments)

    return {"type": "text", "text": f"Unknown tool: {name}"}


async def run_web_server(port: int) -> None:
    """Run the web management server.

    Args:
        port: Port to run the web server on

    Raises:
        ValueError: ポート番号が無効な場合
        OSError: ポートが既に使用中の場合
    """
    # ポート番号の検証
    if not MIN_PORT <= port <= MAX_PORT:
        msg = f"ポート番号は{MIN_PORT}から{MAX_PORT}の範囲で指定してください: {port}"
        raise ValueError(msg)

    web_app = create_app()
    # 環境変数からログレベルを取得（デフォルト: warning）
    web_log_level = os.getenv("ACEMCP_WEB_LOG_LEVEL", "warning").lower()

    config_uvicorn = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=port,
        log_level=web_log_level,
        access_log=False,  # Disable access log to reduce noise
    )
    server = uvicorn.Server(config_uvicorn)
    try:
        await server.serve()
    except OSError as e:
        if "Address already in use" in str(e) or "アドレスは既に使用中です" in str(e):
            logger.error(f"ポート{port}は既に使用中です。別のポートを指定してください。")
        raise


def setup_signal_handlers(shutdown_event: asyncio.Event) -> None:
    """シグナルハンドラーを設定します。

    Args:
        shutdown_event: シャットダウンイベント
    """

    def handle_signal(signum: int, frame: Any) -> None:
        """シグナルを処理します。"""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}, shutting down gracefully...")

        # イベントループを取得してシャットダウンイベントをセット
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(shutdown_event.set)
        except RuntimeError:
            logger.warning("No running event loop, setting shutdown event directly")
            # イベントループが実行中でない場合は直接セット
            shutdown_event.set()

    # SIGINTとSIGTERMを処理
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)


async def main(
    base_url: str | None = None, token: str | None = None, web_port: int | None = None
) -> None:
    """Run the MCP server.

    Args:
        base_url: Override BASE_URL from command line
        token: Override TOKEN from command line
        web_port: Port for web management interface (None to disable)

    Raises:
        ValueError: 設定が無効な場合
        OSError: ファイルシステムエラー
    """
    web_task = None
    mcp_task = None
    shutdown_event = asyncio.Event()

    try:
        # 起動時の検証
        config = init_config(base_url=base_url, token=token)
        config.validate()

        # データディレクトリの書き込み権限チェック
        if not os.access(config.index_storage_path, os.W_OK):
            msg = f"データディレクトリへの書き込み権限がありません: {config.index_storage_path}"
            raise PermissionError(msg)

        logger.info("Starting acemcp MCP server...")
        logger.info(
            f"Configuration: index_storage_path={config.index_storage_path}, "
            f"batch_size={config.batch_size}, token={config.get_masked_token()}"
        )
        logger.info(f"API: base_url={config.base_url}")

        # シグナルハンドラーの設定
        setup_signal_handlers(shutdown_event)

        if web_port:
            logger.info(f"Starting web management interface on port {web_port}")
            web_task = asyncio.create_task(run_web_server(web_port))

        # MCPサーバーをタスクとして起動
        async def run_mcp_server() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await app.run(read_stream, write_stream, app.create_initialization_options())

        mcp_task = asyncio.create_task(run_mcp_server())

        # シャットダウンイベントを待機
        await shutdown_event.wait()
        logger.info("Shutdown event received, stopping server...")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except OSError as e:
        logger.error(f"File system error: {e}")
        raise
    except asyncio.CancelledError:
        logger.info("Server task cancelled")
        raise
    except Exception as e:
        logger.exception("Server error")
        raise
    finally:
        # クリーンアップ
        if mcp_task and not mcp_task.done():
            logger.info("Cancelling MCP server task...")
            mcp_task.cancel()
            try:
                await mcp_task
            except asyncio.CancelledError:
                logger.info("MCP server task cancelled successfully")

        if web_task and not web_task.done():
            logger.info("Cancelling web server task...")
            web_task.cancel()
            try:
                await web_task
            except asyncio.CancelledError:
                logger.info("Web server task cancelled successfully")
        logger.info("Server shutdown complete")


def run() -> None:
    """Entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Acemcp MCP Server for codebase indexing")
    parser.add_argument("--base-url", type=str, help="Override BASE_URL configuration")
    parser.add_argument("--token", type=str, help="Override TOKEN configuration")
    parser.add_argument("--web-port", type=int, help="Enable web management interface on specified port (e.g., 8080)")

    args = parser.parse_args()

    # If web interface is enabled, initialize log broadcaster before setting up logging
    # This ensures the WebSocket handler is preserved
    if args.web_port:
        from acemcp.web.log_handler import get_log_broadcaster
        get_log_broadcaster()  # Initialize the broadcaster

    # Setup logging after log broadcaster is initialized
    setup_logging()

    asyncio.run(main(base_url=args.base_url, token=args.token, web_port=args.web_port))


if __name__ == "__main__":
    run()

