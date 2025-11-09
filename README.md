简体中文 | [English](./README_EN.md)

# Acemcp

代码库索引和语义搜索的 MCP 服务器。

<a href="https://glama.ai/mcp/servers/@qy527145/acemcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@qy527145/acemcp/badge" alt="Acemcp MCP server" />
</a>

## 安装

### 作为工具安装（推荐）

```bash
# 安装到系统
uv tool install acemcp

# 或临时运行（无需安装）
uvx acemcp
```

### 开发安装

```bash
# 克隆仓库
git clone https://github.com/qy527145/acemcp.git
cd acemcp

# 安装依赖
uv sync

# 运行
uv run acemcp
```

## 配置

配置文件会在首次运行时自动创建在 `~/.acemcp/settings.toml`，包含默认值。

编辑 `~/.acemcp/settings.toml` 进行配置：
```toml
BATCH_SIZE = 10
MAX_LINES_PER_BLOB = 800
MAX_CONCURRENT_UPLOADS = 3
MAX_RETRIES = 3
RETRY_DELAY = 1.0
BASE_URL = "https://your-api-endpoint.com/v1"
TOKEN = "your-bearer-token-here"
TEXT_EXTENSIONS = [".py", ".js", ".ts", ...]
EXCLUDE_PATTERNS = [".venv", "node_modules", ".git", "__pycache__", "*.pyc", ...]
```

**配置选项：**
- `BATCH_SIZE`: 每批上传的文件数量（默认：10，范囲：1-100）
- `MAX_LINES_PER_BLOB`: 大文件分割前的最大行数（默认：800，範囲：100-10000）
- `MAX_CONCURRENT_UPLOADS`: 同時アップロード数（デフォルト：3、範囲：1-100）
- `MAX_RETRIES`: 最大リトライ回数（デフォルト：3、範囲：1-10）
- `RETRY_DELAY`: リトライ遅延秒数（デフォルト：1.0、範囲：0.1-60.0）
- `BASE_URL`: API 端点 URL
- `TOKEN`: 認証トークン（マスキングされて表示されます）
- `TEXT_EXTENSIONS`: 要索引的文件扩展名列表
- `EXCLUDE_PATTERNS`: 要排除的模式列表（支持通配符如 `*.pyc`）

您还可以通过以下方式配置：
- **命令行参数**（最高优先级）：`--base-url`、`--token`
- **Web 管理界面**（更新用户配置文件）
- **环境变量**（使用 `ACEMCP_` 前缀）

## MCP 配置

将以下内容添加到您的 MCP 客户端配置中（例如 Claude Desktop）：

### 基础配置

```json
{
  "mcpServers": {
    "acemcp": {
      "command": "uvx",
      "args": [
        "acemcp"
      ]
    }
  }
}
```


**可用的命令行参数：**
- `--base-url`: 覆盖 BASE_URL 配置
- `--token`: 覆盖 TOKEN 配置
- `--web-port`: 在指定端口启用 Web 管理界面（例如 8080）

### 启用 Web 管理界面的配置

要启用 Web 管理界面，添加 `--web-port` 参数：

```json
{
  "mcpServers": {
    "acemcp": {
      "command": "uvx",
      "args": [
        "acemcp",
        "--web-port",
        "8888"
      ]
    }
  }
}
```

然后访问管理界面：`http://localhost:8888`

**Web 管理功能：**
- **配置管理**：查看和编辑服务器配置（BASE_URL、TOKEN（マスキング表示）、BATCH_SIZE、MAX_LINES_PER_BLOB、MAX_CONCURRENT_UPLOADS、MAX_RETRIES、RETRY_DELAY、TEXT_EXTENSIONS）
- **实时日志**：通过 WebSocket 连接实时监控服务器日志，具有智能重连功能
  - 指数退避重连策略（1秒 → 1.5秒 → 2.25秒 ... 最大 30秒）
  - 最多 10 次重连尝试，防止无限循环
  - 网络故障时自动重连
  - 减少日志噪音（WebSocket 连接记录在 DEBUG 级别）
- **工具调试器**：直接从 Web 界面测试和调试 MCP 工具
  - 测试 `search_context` 工具，输入项目路径和查询
  - 查看格式化的结果和错误消息

## 工具

### search_context

基于查询搜索相关的代码上下文。此工具在搜索前**自动执行增量索引**，确保结果始终是最新的。它在您的代码库中执行**语义搜索**，并返回格式化的文本片段，显示相关代码的位置。

**核心特性：**
- **自动增量索引**：每次搜索前，工具自动仅索引新文件或修改过的文件，跳过未更改的文件以提高效率
- **无需手动索引**：您无需手动索引项目 - 只需搜索，工具会自动处理索引
- **始终保持最新**：搜索结果反映代码库的当前状态
- **多编码支持**：自动检测和处理多种文件编码（UTF-8、GBK、GB2312、Latin-1）
- **.gitignore 集成**：索引项目时自动遵守 `.gitignore` 模式

**参数：**
- `project_root_path`（字符串）：项目根目录的绝对路径
  - **重要**：即使在 Windows 上也使用正斜杠（`/`）作为路径分隔符
  - Windows 示例：`C:/Users/username/projects/myproject`
  - Linux/Mac 示例：`/home/username/projects/myproject`
- `query`（字符串）：用于查找相关代码上下文的自然语言搜索查询
  - 使用与您要查找的内容相关的描述性关键词
  - 工具执行语义匹配，而不仅仅是关键词搜索
  - 返回带有文件路径和行号的代码片段

**返回内容：**
- 与您的查询匹配的文件中的格式化文本片段
- 每个片段的文件路径和行号
- 相关代码部分周围的上下文
- 按相关性排序的多个结果

**查询示例：**

1. **查找配置代码：**
   ```json
   {
     "project_root_path": "C:/Users/username/projects/myproject",
     "query": "日志配置 设置 初始化 logger"
   }
   ```
   返回：与日志设置、logger 初始化和配置相关的代码

2. **查找认证逻辑：**
   ```json
   {
     "project_root_path": "C:/Users/username/projects/myproject",
     "query": "用户认证 登录 密码验证"
   }
   ```
   返回：认证处理器、登录函数、密码验证代码

3. **查找数据库代码：**
   ```json
   {
     "project_root_path": "C:/Users/username/projects/myproject",
     "query": "数据库连接池 初始化"
   }
   ```
   返回：数据库连接设置、连接池配置、初始化代码

4. **查找错误处理：**
   ```json
   {
     "project_root_path": "C:/Users/username/projects/myproject",
     "query": "错误处理 异常 try catch"
   }
   ```
   返回：错误处理模式、异常处理器、try-catch 块

5. **查找 API 端点：**
   ```json
   {
     "project_root_path": "C:/Users/username/projects/myproject",
     "query": "API 端点 路由 HTTP 处理器"
   }
   ```
   返回：API 路由定义、HTTP 处理器、端点实现

**获得更好结果的技巧：**
- 使用多个相关关键词（例如，"日志配置设置"而不仅仅是"日志"）
- 包含您要查找的特定技术术语
- 描述功能而不是确切的变量名
- 如果第一次查询没有返回您需要的内容，尝试不同的措辞

**索引特性：**
- **增量索引**：仅上传新文件或修改过的文件，跳过未更改的文件
- **基于哈希的去重**：通过路径 + 内容的 SHA-256 哈希识别文件
- **自动重试**：网络请求自动重试最多 3 次，采用指数退避（1秒、2秒、4秒）
- **批次弹性**：如果批次上传在重试后失败，工具会继续处理下一批次
- **文件分割**：大文件自动分割为多个块（默认：每块 800 行）
- **排除模式**：自动跳过虚拟环境、node_modules、.git、构建产物等
- **多编码支持**：自动检测文件编码（UTF-8、GBK、GB2312、Latin-1），并在失败时回退到 UTF-8 错误处理
- **.gitignore 集成**：自动从项目根目录加载并遵守 `.gitignore` 模式，与配置的排除模式结合使用

**搜索特性：**
- **自动重试**：搜索请求自动重试最多 3 次，采用指数退避（2秒、4秒、8秒）
- **优雅降级**：如果所有重试后搜索失败，返回清晰的错误消息
- **超时处理**：使用 60 秒超时来处理长时间运行的搜索
- **空结果处理**：如果未找到相关代码，返回有用的消息

**默认排除模式：**
```
.venv, venv, .env, env, node_modules, .git, .svn, .hg, __pycache__,
.pytest_cache, .mypy_cache, .tox, .eggs, *.egg-info, dist, build,
.idea, .vscode, .DS_Store, *.pyc, *.pyo, *.pyd, .Python,
pip-log.txt, pip-delete-this-directory.txt, .coverage, htmlcov,
.gradle, target, bin, obj
```
模式支持通配符（`*`、`?`），并匹配目录/文件名或路径。

**注意：** 如果项目根目录存在 `.gitignore` 文件，其模式将自动加载并与配置的排除模式结合使用。`.gitignore` 模式遵循 Git 的标准 wildmatch 语法。

## 高级特性

### 多编码文件支持

Acemcp 自动检测和处理不同字符编码的文件，适用于国际化项目：

- **自动检测**：按顺序尝试多种编码：UTF-8 → GBK → GB2312 → Latin-1
- **回退处理**：如果所有编码都失败，使用 UTF-8 错误处理以防止崩溃
- **日志记录**：记录每个文件成功使用的编码（DEBUG 级别）
- **无需配置**：开箱即用，支持大多数常见编码

这对以下情况特别有用：
- 混合编码文件的项目（例如，UTF-8 源代码 + GBK 文档）
- 使用非 UTF-8 编码的遗留代码库
- 具有不同语言文件的国际团队

### .gitignore 集成

Acemcp 自动遵守您项目的 `.gitignore` 文件：

- **自动加载**：如果存在，从项目根目录读取 `.gitignore`
- **标准语法**：支持 Git 的标准 wildmatch 模式
- **组合过滤**：与配置的 `EXCLUDE_PATTERNS` 一起工作
- **目录处理**：正确处理带有尾部斜杠的目录模式
- **无需配置**：只需在项目根目录放置 `.gitignore`

**`.gitignore` 模式示例：**
```gitignore
# 依赖
node_modules/
vendor/

# 构建输出
dist/
build/
*.pyc

# IDE 文件
.vscode/
.idea/

# 环境文件
.env
.env.local
```

所有这些模式在索引期间都会自动遵守,并与默认排除模式结合使用。

## セキュリティ

Acemcp は、安全な操作を確保するための複数のセキュリティ機能を実装しています：

### トークン管理

- **トークンマスキング**: ログと Web API でトークンが自動的にマスキングされます（例: `abcd****wxyz`）
- **安全な保存**: 設定ファイルは推奨パーミッション（600）で保護されます
- **環境変数**: コマンドライン引数または環境変数でトークンを上書きできます

### パス検証

- **パストラバーサル防止**: すべてのパスが検証され、`..`パターンが拒否されます
- **絶対パス検証**: プロジェクトパスは絶対パスである必要があります
- **シンボリックリンク解決**: パスは安全性チェック後に正規化されます
- **権限チェック**: ファイルシステムアクセス前に読み取り権限を検証します

### 入力バリデーション

- **パス長制限**: 最大 4096 文字
- **クエリ長制限**: 最大 10000 文字
- **URL 検証**: base_url は有効な HTTP/HTTPS URL である必要があります
- **ファイル拡張子検証**: 拡張子は `.` で始まる必要があります
- **除外パターン検証**: 危険なパターン（システムディレクトリ）が拒否されます

### ログセキュリティ

- **センシティブ情報のマスキング**: ログ内のトークン、パスワード、API キーが自動的にマスキングされます
- **フィルタリングパターン**:
  - Bearer トークン: `Bearer ****`
  - API キー: `api_key=****`
  - パスワード: `password=****`

**セキュリティのベストプラクティス:**
```bash
# 設定ファイルの権限を設定
chmod 600 ~/.acemcp/settings.toml

# 環境変数を使用
export ACEMCP_TOKEN="your-token"

# または、コマンドライン引数を使用
acemcp --token "your-token"
```

## パフォーマンス最適化

Acemcp は、高速かつ効率的な操作のために最適化されています：

### 並行バッチアップロード

- **並列処理**: バッチが同時にアップロードされます（デフォルト: 3）
- **セマフォ制御**: 同時実行数を制限してリソースを保護します
- **設定可能**: `MAX_CONCURRENT_UPLOADS` で制御できます

### メモリ効率

- **チャンク読み込み**: 大きなファイル（>10MB）がチャンクで読み込まれます
- **エンコーディング検出**: 最初の 8KB のみを使用して効率的にエンコーディングを検出します
- **ストリーミング処理**: ファイルが順次処理されてメモリ使用量を削減します

### キャッシング

- **.gitignore キャッシング**: 同じプロジェクトで .gitignore が再読み込みされません
- **設定キャッシング**: Web API レスポンスが 5 秒間キャッシュされます
- **ステータスキャッシング**: ステータスクエリが 5 秒間キャッシュされます

### リトライ戦略

- **エクスポネンシャルバックオフ**: 1秒 → 2秒 → 4秒 （最大 3 回のリトライ）
- **スマートリトライ**: タイムアウトとネットワークエラーのみをリトライします
- **非リトライエラー**: 4xx HTTP エラーは即座に失敗します

**パフォーマンスチューニング:**
```toml
# ~/.acemcp/settings.toml
BATCH_SIZE = 20  # より大きなバッチサイズ（1-100）
MAX_CONCURRENT_UPLOADS = 5  # より多くの並行アップロード
MAX_LINES_PER_BLOB = 1000  # より大きなチャンク（100-10000）
```

**環境変数:**
```bash
# ログレベルを調整
export ACEMCP_LOG_LEVEL=WARNING  # デフォルト: INFO

# Web ログレベルを調整
export ACEMCP_WEB_LOG_LEVEL=error  # デフォルト: warning

# CORS を有効化（本番環境での外部アクセスに必要）
export ACEMCP_ENABLE_CORS=true  # デフォルト: false
export ACEMCP_ALLOWED_ORIGINS="https://example.com,https://app.example.com"  # デフォルト: "*"
```

**CORS 設定:**
- `ACEMCP_ENABLE_CORS`: CORS を有効にする（デフォルト: false）
- `ACEMCP_ALLOWED_ORIGINS`: 許可するオリジンのカンマ区切りリスト（デフォルト: "*"）

**レート制限:**
Web API のデフォルトレート制限は **10 リクエスト/分** です。この制限は `slowapi` により実装されています。

## トラブルシューティング

### 一般的な問題と解決策

#### 認証エラー

```
Error: 401 Unauthorized
```

**解決策:**
1. `~/.acemcp/settings.toml` で TOKEN を確認します
2. トークンが有効で期限切れでないことを確認します
3. トークンに先頭/末尾のスペースがないことを確認します

#### ネットワークタイムアウト

```
Error: Request failed after 3 retries
```

**解決策:**
1. ネットワーク接続を確認します
2. BASE_URL が到達可能であることを確認します
3. ファイアウォール設定を確認します
4. より長いタイムアウトのために定数を調整します

#### ファイルエンコーディングエラー

```
Warning: Read file.txt with utf-8 and errors='ignore' (some characters may be lost)
```

**解決策:**
1. これは通常、安全な警告です（フォールバック機能）
2. 重要な場合は、ファイルを UTF-8 に変換します
3. SUPPORTED_ENCODINGS にカスタムエンコーディングを追加します

#### メモリ不足

```
MemoryError: Unable to allocate memory
```

**解決策:**
1. BATCH_SIZE を減らします（例: 5）
2. MAX_LINES_PER_BLOB を減らします（例: 500）
3. より多くのファイルを除外します
4. 大きなファイルを小さなチャンクに分割します

#### ポートが既に使用中

```
OSError: Address already in use
```

**解決策:**
1. 別の `--web-port` を使用します
2. 既存のプロセスを停止します: `lsof -i :8888`
3. または: `kill -9 $(lsof -t -i :8888)`

### デバッグ

詳細なデバッグ情報を有効にします:

```bash
# DEBUG レベルのログを有効にします
export ACEMCP_LOG_LEVEL=DEBUG
acemcp --web-port 8888

# ログファイルを確認します
tail -f ~/.acemcp/log/acemcp.log

# Web インターフェースで実時間ログを表示します
# http://localhost:8888 にアクセス
```

## ベストプラクティス

### 効果的なクエリ

✅ **良い:**
```
"logging configuration setup initialization"
"database connection pool initialization"
"error handling exception middleware"
```

❌ **悪い:**
```
"code"  # あまりにも一般的
"x"     # あまりにも短い
"function" # あまりにも曖昧
```

### 除外パターン

効率的なパフォーマンスのために適切なパターンを設定します:

```toml
EXCLUDE_PATTERNS = [
    # ビルドアーティファクト
    "dist", "build", "target",
    
    # 依存関係
    "node_modules", ".venv", "vendor",
    
    # 生成されたファイル
    "*.pyc", "*.class", "*.o",
    
    # 大きなデータファイル
    "*.log", "*.db", "*.sqlite",
    
    # IDE/エディタ
    ".idea", ".vscode", "*.swp"
]
```

### 大規模プロジェクト

大規模なコードベースのインデックス化:

1. **段階的インデックス化**: サブディレクトリから開始します
2. **バッチサイズの調整**: ネットワーク速度に基づいて調整します
3. **除外の最適化**: 不要なファイルを積極的に除外します
4. **監視**: Web インターフェースを使用して進行状況を追跡します

```toml
# 大規模プロジェクトの設定
BATCH_SIZE = 15
MAX_LINES_PER_BLOB = 1000
MAX_CONCURRENT_UPLOADS = 3
```

### パフォーマンスチューニング

システムリソースに基づいて調整します:

```toml
# 高速ネットワーク + 強力なマシン
BATCH_SIZE = 20
MAX_CONCURRENT_UPLOADS = 5

# 低速ネットワーク + 制限されたリソース
BATCH_SIZE = 5
MAX_CONCURRENT_UPLOADS = 2

# バランスの取れた設定（推奨）
BATCH_SIZE = 10
MAX_CONCURRENT_UPLOADS = 3
```

## 使用方法

1. 启动 MCP 服务器（由 MCP 客户端自动启动）
2. 使用 `search_context` 搜索代码上下文
   - 工具在搜索前自动索引您的项目
   - 增量索引确保仅上传新文件/修改过的文件
   - 无需手动索引步骤！
   - 无论编码如何，文件都会自动处理
   - 自动遵守 `.gitignore` 模式

## 数据存储

- **配置**：`~/.acemcp/settings.toml`
- **已索引项目**：`~/.acemcp/data/projects.json`（固定位置）
- **日志文件**：`~/.acemcp/log/acemcp.log`（自动轮转）
- 项目通过其绝对路径识别（使用正斜杠规范化）

## 日志记录

应用程序自动记录日志到 `~/.acemcp/log/acemcp.log`，具有以下特性：

- **控制台输出**：INFO 级别及以上（彩色输出）
- **文件输出**：DEBUG 级别及以上（详细格式，包含模块、函数和行号）
- **自动轮转**：日志文件达到 5MB 时自动轮转
- **保留策略**：最多保留 10 个日志文件
- **压缩**：轮转的日志文件自动压缩为 `.zip` 格式
- **线程安全**：日志记录对并发操作是线程安全的

**日志格式：**
```
2025-11-06 13:51:25 | INFO     | acemcp.server:main:103 - Starting acemcp MCP server...
```

日志文件在首次运行时自动创建，无需手动配置。

## Web 管理界面

Web 管理界面提供：
- **实时服务器状态**监控
- **实时日志流**通过 WebSocket
- **配置查看**（当前设置）
- **项目统计**（已索引项目数量）

要启用 Web 界面，在启动服务器时使用 `--web-port` 参数。

**功能：**
- 带自动滚动的实时日志显示
- 服务器状态和指标
- 配置概览
- 使用 Tailwind CSS 的响应式设计
- 无需构建步骤（使用 CDN 资源）
- 具有指数退避的智能 WebSocket 重连

## 最近更新

### 版本 0.1.5（最新）

**セキュリティ強化：**
- 🔐 **トークンマスキング**: ログと Web API でトークンが自動的にマスキングされます
- 🔐 **パス検証**: パストラバーサル攻撃防止と厳密なパス検証
- 🔐 **入力バリデーション**: すべての入力に対する包括的なバリデーション（パス、クエリ、URL、拡張子）
- 🔐 **センシティブ情報フィルタリング**: ログメッセージ内のトークン、パスワード、API キーのマスキング
- 🔐 **設定ファイル権限**: 自動的にセキュアな権限（600）に設定されます

**パフォーマンス最適化：**
- ⚡ **並行バッチアップロード**: 複数のバッチが同時にアップロードされます（デフォルト: 3）
- ⚡ **メモリ効率**: 大きなファイル（>10MB）のチャンク読み込みとストリーミング処理
- ⚡ **キャッシング**: .gitignore、設定、ステータスのキャッシング
- ⚡ **スマートエンコーディング検出**: 最初の 8KB のみを使用した効率的な検出
- ⚡ **改善されたリトライロジック**: リトライ可能なエラーとそうでないエラーの明確な区別

**エラーハンドリングの改善：**
- 🛠️ **具体的な例外処理**: 広範な Exception キャッチの代わりに特定の例外タイプ
- 🛠️ **詳細なエラーメッセージ**: すべてのエラーにコンテキスト情報を含む
- 🛠️ **グレースフルシャットダウン**: 適切なシグナル処理と clean

up
- 🛠️ **エラー分類**: リトライ可能/不可能なエラーの明確な区別

**コード品質向上：**
- 📝 **型ヒントの改善**: すべてのモジュールに完全な型ヒントを追加
- 📝 **ドキュメントの強化**: 詳細な docstring とコメント
- 📝 **定数の集約**: すべてのマジックナンバーを constants.py に移動
- 📝 **ユーティリティ関数**: 共通機能を utils.py に集約

**WebSocket の強化:**
- 🌐 **スレッドセーフティ**: asyncio.Lock による適切な同期
- 🌐 **クライアント制限**: 最大 100 クライアント
- 🌐 **キューサイズ制限**: クライアントごとに最大 1000 メッセージ
- 🌐 **タイムアウト処理**: 60 秒の非アクティブ後に自動切断
- 🌐 **メモリリーク防止**: 適切なクライアントクリーンアップ

**Web API の改善:**
- 🔧 **入力バリデーション**: Pydantic バリデータによる設定更新の検証
- 🔧 **レスポンスキャッシング**: 設定とステータスのキャッシング（5 秒 TTL）
- 🔧 **エラーレスポンスの標準化**: 一貫したエラー形式
- 🔧 **型安全性**: すべてのエンドポイントに完全な型ヒント

**開発ツール:**
- 🔨 **テストフレームワーク**: pytest、pytest-asyncio、pytest-cov を追加
- 🔨 **型チェック**: mypy 設定を追加
- 🔨 **Ruff 改善**: より良いコード品質のためにルールを調整

### 版本 0.1.4

**新特性：**
- ✨ **多编码支持**：自動检测和处理多种文件编码（UTF-8、GBK、GB2312、Latin-1）
- ✨ **.gitignore 集成**：自動从项目根目录加载并遵守 `.gitignore` 模式
- ✨ **改进的工具响应格式**：从基于列表的格式改为基于字典的格式，以提高客户端兼容性

**改进：**
- 🔧 **WebSocket 优化**：具有指数退避的智能重连（1秒 → 最大 30秒）
- 🔧 **减少日志噪音**：WebSocket 连接现在记录在 DEBUG 级别而不是 INFO
- 🔧 **连接稳定性**：最多 10 次重连尝试，防止无限循环
- 🔧 **更好的错误处理**：对无法用任何编码解码的文件进行优雅回退

**错误修复：**
- 🐛 修复了频繁的 WebSocket 连接/断开循环
- 🐛 修复了读取非 UTF-8 编码文件时的编码错误
- 🐛 改进了对带有目录匹配的 .gitignore 模式的处理