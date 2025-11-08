# API参考

<cite>
**本文档引用的文件**
- [search_context.py](file://src/acemcp/tools/search_context.py)
- [app.py](file://src/acemcp/web/app.py)
- [log_handler.py](file://src/acemcp/web/log_handler.py)
- [config.py](file://src/acemcp/config.py)
- [manager.py](file://src/acemcp/index/manager.py)
- [index.html](file://src/acemcp/web/templates/index.html)
</cite>

## 目录
1. [MCP协议接口](#mcp协议接口)
2. [Web API](#web-api)
3. [WebSocket接口](#websocket接口)
4. [错误码列表](#错误码列表)

## MCP协议接口

### search_context工具调用规范

`search_context`工具用于基于查询搜索代码上下文，支持自动增量索引和语义搜索。

**参数类型与约束：**

- `project_root_path`（字符串）
  - **语义**：项目根目录的绝对路径
  - **约束**：
    - 必需参数，不能为空
    - 必须使用正斜杠（`/`）作为路径分隔符，即使在Windows系统上
    - 路径必须存在且可访问
  - **示例**：
    - Windows: `C:/Users/username/projects/myproject`
    - Linux/Mac: `/home/username/projects/myproject`

- `query`（字符串）
  - **语义**：用于查找相关代码上下文的自然语言搜索查询
  - **约束**：
    - 必需参数，不能为空
    - 支持语义匹配而非简单关键词搜索
    - 建议使用多个相关关键词以提高搜索质量
  - **示例**：
    - `"日志配置 设置 初始化 logger"`
    - `"用户认证 登录 密码验证"`
    - `"数据库连接池 初始化"`

**返回值语义：**
- 返回包含搜索结果的字典，格式为 `{"type": "text", "text": "结果内容"}`
- 结果内容包含与查询匹配的代码片段，包括文件路径、行号和上下文
- 按相关性排序的多个结果
- 如果搜索失败，返回错误信息

**调用示例（Python客户端）：**
```python
import asyncio
from mcp.client import StdioClient

async def search_code_context():
    client = StdioClient("acemcp")
    await client.connect()
    
    result = await client.call_tool(
        "search_context",
        {
            "project_root_path": "C:/Users/username/projects/myproject",
            "query": "日志配置 设置 初始化 logger"
        }
    )
    
    print(result["text"])
    await client.disconnect()

asyncio.run(search_code_context())
```

**调用示例（curl命令）：**
```bash
# 注意：MCP协议通常通过stdio通信，以下为模拟HTTP调用示例
curl -X POST http://localhost:8080/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_context",
    "arguments": {
      "project_root_path": "C:/Users/username/projects/myproject",
      "query": "日志配置 设置 初始化 logger"
    }
  }'
```

**Section sources**
- [search_context.py](file://src/acemcp/tools/search_context.py#L10-L49)
- [manager.py](file://src/acemcp/index/manager.py#L467-L549)
- [server.py](file://src/acemcp/server.py#L49-L53)

## Web API

使用OpenAPI标准文档化的REST端点。

### /api/config (GET)

获取当前配置信息。

**HTTP方法**：GET

**请求头**：
- 无特殊要求

**请求参数**：无

**响应JSON Schema**：
```json
{
  "type": "object",
  "properties": {
    "index_storage_path": {"type": "string"},
    "batch_size": {"type": "integer"},
    "max_lines_per_blob": {"type": "integer"},
    "base_url": {"type": "string"},
    "token": {"type": "string"},
    "token_full": {"type": "string"},
    "text_extensions": {"type": "array", "items": {"type": "string"}},
    "exclude_patterns": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["index_storage_path", "batch_size", "max_lines_per_blob", "base_url", "token", "text_extensions", "exclude_patterns"]
}
```

**状态码**：
- `200 OK`：成功获取配置
- `500 Internal Server Error`：服务器内部错误

**认证要求**：无

**Python客户端调用示例**：
```python
import requests

response = requests.get("http://localhost:8080/api/config")
if response.status_code == 200:
    config = response.json()
    print(f"批处理大小: {config['batch_size']}")
    print(f"最大行数: {config['max_lines_per_blob']}")
else:
    print(f"请求失败: {response.status_code}")
```

**curl命令示例**：
```bash
curl -X GET http://localhost:8080/api/config
```

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L58-L71)
- [config.py](file://src/acemcp/config.py#L118-L164)

### /api/config (POST)

更新服务器配置。

**HTTP方法**：POST

**请求头**：
- `Content-Type: application/json`

**请求JSON Schema**：
```json
{
  "type": "object",
  "properties": {
    "base_url": {"type": "string", "nullable": true},
    "token": {"type": "string", "nullable": true},
    "batch_size": {"type": "integer", "nullable": true},
    "max_lines_per_blob": {"type": "integer", "nullable": true},
    "text_extensions": {"type": "array", "items": {"type": "string"}, "nullable": true},
    "exclude_patterns": {"type": "array", "items": {"type": "string"}, "nullable": true}
  }
}
```

**响应JSON Schema**：
```json
{
  "type": "object",
  "properties": {
    "status": {"type": "string"},
    "message": {"type": "string"}
  },
  "required": ["status", "message"]
}
```

**状态码**：
- `200 OK`：配置更新成功
- `404 Not Found`：用户配置文件未找到
- `500 Internal Server Error`：配置更新失败

**认证要求**：无

**Python客户端调用示例**：
```python
import requests

config_update = {
    "batch_size": 20,
    "max_lines_per_blob": 1000,
    "text_extensions": [".py", ".js", ".ts", ".java"]
}

response = requests.post("http://localhost:8080/api/config", json=config_update)
if response.status_code == 200:
    result = response.json()
    print(result["message"])
else:
    print(f"更新失败: {response.status_code} - {response.json().get('detail', 'Unknown error')}")
```

**curl命令示例**：
```bash
curl -X POST http://localhost:8080/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "batch_size": 20,
    "max_lines_per_blob": 1000,
    "text_extensions": [".py", ".js", ".ts", ".java"]
  }'
```

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L74-L118)
- [config.py](file://src/acemcp/config.py#L80-L104)

### /api/status (GET)

获取服务器状态信息。

**HTTP方法**：GET

**请求头**：
- 无特殊要求

**请求参数**：无

**响应JSON Schema**：
```json
{
  "type": "object",
  "properties": {
    "status": {"type": "string"},
    "project_count": {"type": "integer"},
    "storage_path": {"type": "string"}
  },
  "required": ["status", "project_count", "storage_path"]
}
```

**状态码**：
- `200 OK`：成功获取状态
- `500 Internal Server Error`：服务器内部错误

**认证要求**：无

**Python客户端调用示例**：
```python
import requests

response = requests.get("http://localhost:8080/api/status")
if response.status_code == 200:
    status = response.json()
    print(f"服务器状态: {status['status']}")
    print(f"项目数量: {status['project_count']}")
    print(f"存储路径: {status['storage_path']}")
else:
    print(f"请求失败: {response.status_code}")
```

**curl命令示例**：
```bash
curl -X GET http://localhost:8080/api/status
```

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L121-L137)
- [config.py](file://src/acemcp/config.py#L80-L80)

### /api/tools/execute (POST)

执行工具调试，主要用于测试MCP工具。

**HTTP方法**：POST

**请求头**：
- `Content-Type: application/json`

**请求JSON Schema**：
```json
{
  "type": "object",
  "properties": {
    "tool_name": {"type": "string"},
    "arguments": {"type": "object"}
  },
  "required": ["tool_name", "arguments"]
}
```

**响应JSON Schema**：
```json
{
  "type": "object",
  "properties": {
    "status": {"type": "string"},
    "result": {"type": "object", "nullable": true},
    "message": {"type": "string", "nullable": true}
  },
  "required": ["status"]
}
```

**状态码**：
- `200 OK`：工具执行成功
- `400 Bad Request`：请求参数无效
- `500 Internal Server Error`：工具执行失败

**认证要求**：无

**Python客户端调用示例**：
```python
import requests

tool_request = {
    "tool_name": "search_context",
    "arguments": {
        "project_root_path": "C:/Users/username/projects/myproject",
        "query": "日志配置"
    }
}

response = requests.post("http://localhost:8080/api/tools/execute", json=tool_request)
if response.status_code == 200:
    result = response.json()
    if result["status"] == "success":
        print("工具执行成功:")
        print(result["result"]["text"])
    else:
        print(f"工具执行失败: {result['message']}")
else:
    print(f"请求失败: {response.status_code}")
```

**curl命令示例**：
```bash
curl -X POST http://localhost:8080/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_context",
    "arguments": {
      "project_root_path": "C:/Users/username/projects/myproject",
      "query": "日志配置"
    }
  }'
```

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L139-L167)
- [search_context.py](file://src/acemcp/tools/search_context.py#L10-L49)

## WebSocket接口

### /ws/logs 端点

提供实时日志流功能。

**连接建立：**
- 使用WebSocket协议连接
- URL格式：`ws://localhost:端口/ws/logs` 或 `wss://域名:端口/ws/logs`
- 连接成功后，服务器会接受连接并开始发送日志消息
- 客户端需要处理连接、消息接收、错误和关闭事件

**消息格式：**
- **类型**：文本消息
- **内容**：日志条目，格式为 `YYYY-MM-DD HH:mm:ss | LEVEL | 模块:函数:行号 - 消息内容`
- **时间戳**：ISO 8601格式的时间戳，包含年、月、日、时、分、秒
- **级别**：日志级别（INFO、WARNING、ERROR、DEBUG等）

**实时流特性：**
- **自动重连**：支持指数退避重连策略（1秒 → 1.5秒 → 2.25秒 ... 最大30秒）
- **重连限制**：最多10次重连尝试，防止无限循环
- **自动滚动**：客户端通常实现自动滚动到底部功能
- **消息缓冲**：建议客户端限制日志消息数量（如最多500条），旧消息自动移除
- **连接管理**：支持手动断开和重新连接

**Python客户端调用示例**：
```python
import asyncio
import websockets
import json

async def connect_to_logs():
    uri = "ws://localhost:8080/ws/logs"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("已连接到日志流...")
                
                while True:
                    try:
                        message = await websocket.recv()
                        print(f"日志: {message}")
                    except websockets.exceptions.ConnectionClosed:
                        print("连接已关闭，准备重连...")
                        break
                    except Exception as e:
                        print(f"接收消息错误: {e}")
                        break
                        
        except Exception as e:
            print(f"连接错误: {e}")
            # 指数退避重连
            await asyncio.sleep(1)
            continue

# 运行日志客户端
asyncio.run(connect_to_logs())
```

**curl命令示例：**
```bash
# curl不直接支持WebSocket，使用websocat工具替代
# 首先安装websocat: cargo install websocat
websocat ws://localhost:8080/ws/logs
```

**JavaScript客户端示例（浏览器）：**
```javascript
function setupWebSocketLogs() {
    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    const initialReconnectDelay = 1000; // 1秒
    
    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('WebSocket连接成功');
            reconnectAttempts = 0; // 重置重连计数
        };
        
        ws.onmessage = (event) => {
            const logMessage = event.data;
            console.log(`实时日志: ${logMessage}`);
            // 在UI中添加日志消息
            addLogToUI(logMessage);
        };
        
        ws.onclose = (event) => {
            console.log(`WebSocket连接关闭: ${event.code}`);
            
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                const delay = Math.min(initialReconnectDelay * Math.pow(1.5, reconnectAttempts - 1), 30000); // 最大30秒
                console.log(`将在${delay}ms后重连... (${reconnectAttempts}/${maxReconnectAttempts})`);
                
                setTimeout(connect, delay);
            } else {
                console.warn('达到最大重连次数，请刷新页面');
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket错误:', error);
        };
    }
    
    // 开始连接
    connect();
    
    // 返回控制函数
    return {
        disconnect: () => {
            if (ws) {
                ws.close();
            }
        },
        reconnect: () => {
            if (ws) {
                ws.close();
            }
            connect();
        }
    };
}

// 使用示例
const logClient = setupWebSocketLogs();
```

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L169-L187)
- [log_handler.py](file://src/acemcp/web/log_handler.py#L11-L57)
- [index.html](file://src/acemcp/web/templates/index.html#L369-L487)

## 错误码列表

### HTTP错误码

| 状态码 | 名称 | 描述 | 处理建议 |
|--------|------|------|---------|
| 200 | OK | 请求成功 | 正常处理响应数据 |
| 400 | Bad Request | 请求参数无效 | 检查请求JSON格式和参数类型 |
| 404 | Not Found | 资源未找到 | 检查URL路径是否正确 |
| 500 | Internal Server Error | 服务器内部错误 | 检查服务器日志，重试请求 |

### 工具执行错误

| 错误类型 | 描述 | 处理建议 |
|---------|------|---------|
| `project_root_path is required` | 项目根路径参数缺失 | 确保提供`project_root_path`参数 |
| `query is required` | 查询参数缺失 | 确保提供`query`参数 |
| `User configuration file not found` | 用户配置文件不存在 | 检查配置文件路径`~/.acemcp/settings.toml` |
| `Failed to update configuration` | 配置更新失败 | 检查配置文件权限和格式 |
| `Failed to execute tool` | 工具执行失败 | 检查工具名称和参数是否正确 |

### WebSocket连接错误

| 错误场景 | 描述 | 处理建议 |
|---------|------|---------|
| 连接失败 | 无法建立WebSocket连接 | 检查服务器是否运行，端口是否正确 |
| 连接关闭 | WebSocket连接意外关闭 | 实现自动重连机制 |
| 消息接收错误 | 接收消息时发生错误 | 检查网络连接，重新连接 |
| 重连次数超限 | 达到最大重连次数 | 提示用户手动刷新或检查服务器状态 |

### 配置验证错误

| 错误类型 | 描述 | 处理建议 |
|---------|------|---------|
| `BATCH_SIZE must be positive` | 批处理大小必须为正数 | 设置`BATCH_SIZE`为大于0的整数 |
| `MAX_LINES_PER_BLOB must be positive` | 最大行数必须为正数 | 设置`MAX_LINES_PER_BLOB`为大于0的整数 |
| `BASE_URL must be configured` | BASE_URL必须配置 | 在配置文件中设置有效的API端点URL |
| `TOKEN must be configured` | TOKEN必须配置 | 在配置文件中设置有效的认证令牌 |

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L88-L119)
- [config.py](file://src/acemcp/config.py#L151-L164)
- [search_context.py](file://src/acemcp/tools/search_context.py#L26-L30)