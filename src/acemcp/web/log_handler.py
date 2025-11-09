"""Log handler for broadcasting logs to WebSocket clients.

このモジュールは、ログメッセージをWebSocketクライアントにブロードキャストします。
スレッドセーフ、クライアント数制限、キューサイズ制限などの機能を提供します。

重要ログ（ERROR以上）の優先送信メカニズム:
- 重要ログは専用のリングバッファに保存され、キューフル時も確実に送信されます
- 最新N件（デフォルト: 100件）の重要ログが保持されます
"""

import asyncio
from collections import deque
from typing import Any

from loguru import logger

from acemcp.constants import MAX_QUEUE_SIZE, MAX_WEBSOCKET_CLIENTS
from acemcp.utils import mask_sensitive_data

# Global handler ID to prevent duplicate handlers
_global_handler_id: int | None = None

# 重要ログのリングバッファサイズ
PRIORITY_LOG_BUFFER_SIZE = 100


class LogBroadcaster:
    """Broadcast logs to multiple WebSocket clients.

    このクラスは、スレッドセーフなログブロードキャスト機能を提供します。
    クライアント数とキューサイズに制限があり、センシティブ情報はマスキングされます。
    """

    def __init__(self) -> None:
        """Initialize log broadcaster."""
        self.clients: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        # 重要ログ（ERROR以上）のリングバッファ
        self._priority_log_buffer: deque[str] = deque(maxlen=PRIORITY_LOG_BUFFER_SIZE)
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup loguru handler to broadcast logs."""
        global _global_handler_id  # noqa: PLW0603

        # Check if handler is already registered globally
        if _global_handler_id is not None:
            return

        def log_sink(message: Any) -> None:
            """Custom sink to broadcast log messages.

            センシティブ情報をマスキングし、すべてのクライアントに送信します。
            ERROR以上のログは優先バッファに保存されます。
            """
            # recordからログレベルを取得
            record = message.record
            log_level = record["level"].no
            is_priority = log_level >= 40  # ERROR (40) 以上

            log_text = str(message)
            # センシティブ情報のマスキング
            log_text = mask_sensitive_data(log_text)

            # Get the current broadcaster instance to access clients
            if _broadcaster_instance is not None:
                # 重要ログをバッファに保存
                if is_priority:
                    _broadcaster_instance._priority_log_buffer.append(log_text)

                # クライアントリストのコピーを作成（スレッドセーフティ向上）
                clients_snapshot = _broadcaster_instance.clients[:]

                for client_queue in clients_snapshot:
                    try:
                        client_queue.put_nowait(log_text)
                    except asyncio.QueueFull:
                        # キューが満杯の場合
                        if is_priority:
                            # 重要ログの場合は、キューの先頭を削除して挿入
                            try:
                                client_queue.get_nowait()  # 古いメッセージを削除
                                client_queue.put_nowait(log_text)  # 重要ログを挿入
                                logger.debug(f"Priority log forcefully inserted (level: {record['level'].name})")
                            except Exception as e:
                                logger.warning(f"Failed to insert priority log: {e}")
                                asyncio.create_task(_broadcaster_instance._remove_client_async(client_queue))
                        else:
                            # 通常ログの場合はクライアントを削除
                            logger.warning("Client queue full, removing client")
                            asyncio.create_task(_broadcaster_instance._remove_client_async(client_queue))
                    except Exception as e:
                        logger.error(f"Error broadcasting to client: {e}")
                        asyncio.create_task(_broadcaster_instance._remove_client_async(client_queue))

        _global_handler_id = logger.add(
            log_sink,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="INFO",
            filter=lambda record: record["level"].no >= 20,
        )

    async def add_client(self, queue: asyncio.Queue) -> None:
        """Add a client queue.

        新規クライアントには、バッファに保存されている重要ログを送信します。

        Args:
            queue: Client's asyncio queue

        Raises:
            RuntimeError: クライアント数が上限に達している場合
        """
        async with self._lock:
            if len(self.clients) >= MAX_WEBSOCKET_CLIENTS:
                msg = f"Maximum number of WebSocket clients reached ({MAX_WEBSOCKET_CLIENTS})"
                raise RuntimeError(msg)

            self.clients.append(queue)

            # 新規クライアントに重要ログのバッファを送信
            if self._priority_log_buffer:
                for priority_log in list(self._priority_log_buffer):
                    try:
                        queue.put_nowait(priority_log)
                    except asyncio.QueueFull:
                        logger.warning("New client queue full while sending priority logs")
                        break
                logger.info(f"Sent {len(self._priority_log_buffer)} priority logs to new client")

            logger.info(f"WebSocket client added (total: {len(self.clients)})")

    async def remove_client(self, queue: asyncio.Queue) -> None:
        """Remove a client queue.

        Args:
            queue: Client's asyncio queue
        """
        async with self._lock:
            if queue in self.clients:
                self.clients.remove(queue)
                # キューに残っているメッセージをクリア（メモリリーク防止）
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                logger.info(f"WebSocket client removed (total: {len(self.clients)})")

    async def _remove_client_async(self, queue: asyncio.Queue) -> None:
        """非同期でクライアントを削除します（内部使用）。

        Args:
            queue: Client's asyncio queue
        """
        await self.remove_client(queue)


_broadcaster_instance: LogBroadcaster | None = None


def get_log_broadcaster() -> LogBroadcaster:
    """Get the global log broadcaster instance.

    Returns:
        LogBroadcaster instance
    """
    global _broadcaster_instance  # noqa: PLW0603
    if _broadcaster_instance is None:
        _broadcaster_instance = LogBroadcaster()
    return _broadcaster_instance

