"""Search context tool for MCP server."""

import time
from typing import Any

from loguru import logger

from acemcp.config import get_config
from acemcp.constants import MAX_PATH_LENGTH, MAX_QUERY_LENGTH
from acemcp.index import IndexManager
from acemcp.utils import format_error_message


def _validate_arguments(arguments: dict[str, Any]) -> tuple[str, str]:
    """引数を検証します。

    Args:
        arguments: 検証する引数

    Returns:
        tuple: (project_root_path, query)

    Raises:
        ValueError: 引数が無効な場合
    """
    project_root_path = arguments.get("project_root_path")
    query = arguments.get("query")

    # project_root_pathの検証
    if not project_root_path:
        msg = "project_root_path is required"
        raise ValueError(msg)

    if not isinstance(project_root_path, str):
        msg = "project_root_path must be a string"
        raise ValueError(msg)

    project_root_path = project_root_path.strip()
    if not project_root_path:
        msg = "project_root_path cannot be empty or whitespace"
        raise ValueError(msg)

    if len(project_root_path) > MAX_PATH_LENGTH:
        msg = f"project_root_path is too long (max {MAX_PATH_LENGTH} characters)"
        raise ValueError(msg)

    # パストラバーサル攻撃の検出
    if ".." in project_root_path:
        msg = "project_root_path contains invalid characters (path traversal detected)"
        raise ValueError(msg)

    # queryの検証
    if not query:
        msg = "query is required"
        raise ValueError(msg)

    if not isinstance(query, str):
        msg = "query must be a string"
        raise ValueError(msg)

    query = query.strip()
    if not query:
        msg = "query cannot be empty or whitespace"
        raise ValueError(msg)

    if len(query) > MAX_QUERY_LENGTH:
        msg = f"query is too long (max {MAX_QUERY_LENGTH} characters)"
        raise ValueError(msg)

    return project_root_path, query


async def search_context_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Search for code context based on query.

    Args:
        arguments: Tool arguments containing:
            - project_root_path: Absolute path to the project root directory
            - query: Search query string

    Returns:
        Dictionary containing search results

    Examples:
        >>> await search_context_tool({
        ...     "project_root_path": "/path/to/project",
        ...     "query": "logging configuration"
        ... })
        {"type": "text", "text": "...relevant code snippets..."}
    """
    start_time = time.time()

    try:
        # 入力バリデーション
        project_root_path, query = _validate_arguments(arguments)

        logger.info(
            f"Tool invoked: search_context for project {project_root_path} "
            f"with query: {query[:100]}..."
        )

        config = get_config()

        index_manager = IndexManager(
            config.index_storage_path,
            config.base_url,
            config.token,
            config.text_extensions,
            config.batch_size,
            config.max_lines_per_blob,
            config.exclude_patterns,
            max_concurrent_uploads=config.max_concurrent_uploads,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay,
        )
        result = await index_manager.search_context(project_root_path, query)

        elapsed_time = time.time() - start_time
        logger.info(f"search_context completed in {elapsed_time:.2f}s")

        return {"type": "text", "text": result}

    except ValueError as e:
        error_msg = format_error_message(
            e, {"operation": "search_context_tool", "validation": "input"}
        )
        logger.error(error_msg)
        return {
            "type": "text",
            "text": f"Validation Error: {e!s}",
        }
    except FileNotFoundError as e:
        error_msg = format_error_message(
            e, {"operation": "search_context_tool", "path": arguments.get("project_root_path")}
        )
        logger.error(error_msg)
        return {
            "type": "text",
            "text": f"File Not Found Error: {e!s}",
        }
    except PermissionError as e:
        error_msg = format_error_message(
            e, {"operation": "search_context_tool", "path": arguments.get("project_root_path")}
        )
        logger.error(error_msg)
        return {
            "type": "text",
            "text": f"Permission Error: {e!s}",
        }
    except Exception as e:
        error_msg = format_error_message(
            e, {"operation": "search_context_tool", "arguments": str(arguments)[:100]}
        )
        logger.error(error_msg)
        return {
            "type": "text",
            "text": f"Error: {e!s}",
        }

