"""プロジェクト全体で使用される定数の定義。

このモジュールは、acemcpプロジェクト全体で使用される定数を集約し、
一貫性と保守性を向上させます。
"""

# パス関連の定数
MAX_PATH_LENGTH = 4096  # 最大パス長（文字数）
MAX_QUERY_LENGTH = 10000  # 最大クエリ長（文字数）

# リトライ設定の定数
DEFAULT_MAX_RETRIES = 3  # デフォルトのリトライ回数
DEFAULT_RETRY_DELAY = 1.0  # デフォルトのリトライ遅延（秒）
MAX_RETRY_DELAY = 30.0  # 最大リトライ遅延（秒）

# タイムアウト設定の定数
HTTP_CONNECT_TIMEOUT = 10.0  # HTTP接続タイムアウト（秒）
HTTP_READ_TIMEOUT = 30.0  # HTTP読み取りタイムアウト（秒）
HTTP_WRITE_TIMEOUT = 30.0  # HTTP書き込みタイムアウト（秒）
SEARCH_TIMEOUT = 60.0  # 検索タイムアウト（秒）

# バッチ処理の定数
MIN_BATCH_SIZE = 1  # 最小バッチサイズ
MAX_BATCH_SIZE = 100  # 最大バッチサイズ
DEFAULT_MAX_CONCURRENT_UPLOADS = 3  # デフォルトの同時アップロード数

# ファイル処理の定数
MIN_MAX_LINES_PER_BLOB = 100  # 最小行数/blob
MAX_MAX_LINES_PER_BLOB = 10000  # 最大行数/blob
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 大きなファイルの閾値（10MB）
ENCODING_DETECTION_BYTES = 8192  # エンコーディング検出用のバイト数（8KB）

# WebSocket関連の定数
MAX_WEBSOCKET_CLIENTS = 100  # 最大WebSocketクライアント数
MAX_QUEUE_SIZE = 1000  # クライアントキューの最大サイズ
WEBSOCKET_TIMEOUT = 60.0  # WebSocketタイムアウト（秒）

# ログ関連の定数
MAX_LOG_FILES = 10  # 最大ログファイル数（ローテーション保持数）
LOG_ROTATION_SIZE = "5 MB"  # ログローテーションサイズ

# セキュリティ関連の定数
TOKEN_VISIBLE_CHARS = 4  # トークンマスキング時の可視文字数
MIN_PORT = 1024  # 最小ポート番号（システムポートを避ける）
MAX_PORT = 65535  # 最大ポート番号
CONFIG_FILE_MODE = 0o600  # 設定ファイルの推奨パーミッション（オーナーのみ読み書き可能）

# エンコーディング関連の定数
SUPPORTED_ENCODINGS = [
    "utf-8",
    "gbk",
    "gb2312",
    "latin-1",
]  # サポートされるエンコーディングのリスト

# API レート制限の定数
DEFAULT_RATE_LIMIT = "10/minute"  # デフォルトのAPIレート制限（1分あたり10リクエスト）

# キャッシュ関連の定数
CONFIG_CACHE_TTL = 5  # 設定キャッシュのTTL（秒）
STATUS_CACHE_TTL = 5  # ステータスキャッシュのTTL（秒）
