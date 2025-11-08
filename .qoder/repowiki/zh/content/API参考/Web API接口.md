# Web API接口

<cite>
**Referenced Files in This Document**   
- [app.py](file://src/acemcp/web/app.py)
- [config.py](file://src/acemcp/config.py)
- [manager.py](file://src/acemcp/index/manager.py)
- [search_context.py](file://src/acemcp/tools/search_context.py)
</cite>

## 目录
1. [简介](#简介)
2. [API端点](#api端点)
   1. [GET /api/config](#get-apiconfig)
   2. [POST /api/config](#post-apiconfig)
   3. [GET /api/status](#get-apistatus)
   4. [POST /api/tools/execute](#post-apitoolsexecute)
3. [认证机制](#认证机制)
4. [错误处理](#错误处理)
5. [使用示例](#使用示例)

## 简介
本文档详细描述了Acemcp MCP服务器的Web API接口。该API提供配置管理、状态监控和工具调试功能，通过RESTful端点实现。API基于FastAPI框架构建，支持JSON格式的请求和响应。所有端点均需要基于配置令牌的认证，确保系统安全。Web管理界面通过这些API实现配置查看、实时日志和工具调试功能。

## API端点

### GET /api/config
获取当前服务器配置。

**HTTP方法**: `GET`  
**URL**: `/api/config`  
**认证要求**: 是（基于配置令牌）

#### 请求
- **请求头**: 
  - `Authorization: Bearer <token>` - 使用配置中的令牌进行认证

- **请求体**: 无

#### 响应
- **成功响应 (200)**: 返回当前配置信息，其中令牌被掩码处理。

```json
{
  "index_storage_path": "/Users/username/.acemcp/data",
  "batch_size": 10,
  "max_lines_per_blob": 800,
  "base_url": "https://your-api-endpoint.com",
  "token": "***",
  "token_full": "your-bearer-token-here",
  "text_extensions": [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css", ".scss", ".sql", ".sh", ".bash"],
  "exclude_patterns": [".venv", "venv", ".env", "env", "node_modules", ".git", ".svn", ".hg", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", ".eggs", "*.egg-info", "dist", "build", ".idea", ".vscode", ".DS_Store", "*.pyc", "*.pyo", "*.pyd", ".Python", "pip-log.txt", "pip-delete-this-directory.txt", ".coverage", "htmlcov", ".gradle", "target", "bin", "obj"]
}
```

- **错误响应**:
  - `401 Unauthorized`: 未提供或无效的认证令牌
  - `500 Internal Server Error`: 服务器内部错误

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L58-L71)

### POST /api/config
更新服务器配置。

**HTTP方法**: `POST`  
**URL**: `/api/config`  
**认证要求**: 是（基于配置令牌）

#### 请求
- **请求头**: 
  - `Authorization: Bearer <token>` - 使用配置中的令牌进行认证
  - `Content-Type: application/json` - 指定请求体为JSON格式

- **请求体**: `ConfigUpdate` 模型，包含可选的配置更新字段。

| 字段 | 类型 | 描述 | 验证规则 |
|------|------|------|---------|
| `base_url` | 字符串 \| null | API端点URL | 必须为有效URL格式 |
| `token` | 字符串 \| null | 认证令牌 | 长度至少1个字符 |
| `batch_size` | 整数 \| null | 每批上传的文件数量 | 必须为正整数 |
| `max_lines_per_blob` | 整数 \| null | 大文件分割前的最大行数 | 必须为正整数 |
| `text_extensions` | 字符串数组 \| null | 要索引的文件扩展名列表 | 数组元素必须以`.`开头 |
| `exclude_patterns` | 字符串数组 \| null | 要排除的模式列表 | 支持通配符`*`和`?` |

```json
{
  "base_url": "https://new-api-endpoint.com",
  "token": "new-bearer-token",
  "batch_size": 15,
  "max_lines_per_blob": 1000,
  "text_extensions": [".py", ".js", ".ts", ".md"],
  "exclude_patterns": [".venv", "node_modules", ".git", "*.pyc"]
}
```

#### 响应
- **成功响应 (200)**: 配置更新成功，返回成功消息。

```json
{
  "status": "success",
  "message": "Configuration updated and applied successfully!"
}
```

- **错误响应**:
  - `400 Bad Request`: 请求体格式错误
  - `404 Not Found`: 用户配置文件未找到
  - `500 Internal Server Error`: 配置更新失败

#### 配置更新机制
当接收到有效的配置更新请求后，系统执行以下流程：
1. 验证用户配置文件是否存在
2. 读取现有的TOML配置文件
3. 根据请求体中的字段更新配置值
4. 将更新后的配置写回TOML文件
5. 触发配置重载，使新配置立即生效

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L73-L118)
- [config.py](file://src/acemcp/config.py#L140-L150)

### GET /api/status
获取服务器运行状态。

**HTTP方法**: `GET`  
**URL**: `/api/status`  
**认证要求**: 是（基于配置令牌）

#### 请求
- **请求头**: 
  - `Authorization: Bearer <token>` - 使用配置中的令牌进行认证

- **请求体**: 无

#### 响应
- **成功响应 (200)**: 返回服务器状态、已索引项目数量和存储路径。

```json
{
  "status": "running",
  "project_count": 3,
  "storage_path": "/Users/username/.acemcp/data"
}
```

- **错误响应**:
  - `401 Unauthorized`: 未提供或无效的认证令牌
  - `500 Internal Server Error`: 服务器内部错误

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L121-L137)

### POST /api/tools/execute
执行MCP工具进行调试。

**HTTP方法**: `POST`  
**URL**: `/api/tools/execute`  
**认证要求**: 是（基于配置令牌）

#### 请求
- **请求头**: 
  - `Authorization: Bearer <token>` - 使用配置中的令牌进行认证
  - `Content-Type: application/json` - 指定请求体为JSON格式

- **请求体**: `ToolRequest` 模型，指定要执行的工具和参数。

| 字段 | 类型 | 描述 |
|------|------|------|
| `tool_name` | 字符串 | 要执行的工具名称 | 
| `arguments` | 对象 | 工具执行参数 |

```json
{
  "tool_name": "search_context",
  "arguments": {
    "project_root_path": "/Users/username/projects/myproject",
    "query": "用户认证 登录 密码验证"
  }
}
```

#### 响应
- **成功响应 (200)**: 工具执行成功，返回结果。

```json
{
  "status": "success",
  "result": {
    "type": "text",
    "text": "找到相关代码片段..."
  }
}
```

- **错误响应**:
  - `400 Bad Request`: 请求体格式错误
  - `404 Not Found`: 工具未找到
  - `500 Internal Server Error`: 工具执行失败

**Section sources**
- [app.py](file://src/acemcp/web/app.py#L138-L166)
- [search_context.py](file://src/acemcp/tools/search_context.py#L11-L51)

## 认证机制
所有API端点都需要基于令牌的认证。客户端必须在HTTP请求头中包含`Authorization`字段，格式为`Bearer <token>`，其中`<token>`是配置文件中设置的认证令牌。该机制确保只有授权用户才能访问和修改服务器配置。令牌在配置更新时可以被修改，提供灵活的安全管理。

## 错误处理
API采用标准的HTTP状态码进行错误报告：
- `200 OK`: 请求成功
- `400 Bad Request`: 请求格式错误
- `401 Unauthorized`: 认证失败
- `404 Not Found`: 资源未找到
- `500 Internal Server Error`: 服务器内部错误

错误响应通常包含详细的错误消息，帮助客户端诊断问题。例如，配置更新失败时会返回具体的错误原因。

## 使用示例

### curl命令示例
```bash
# 获取配置
curl -X GET "http://localhost:8888/api/config" \
  -H "Authorization: Bearer your-token-here"

# 更新配置
curl -X POST "http://localhost:8888/api/config" \
  -H "Authorization: Bearer your-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "base_url": "https://new-api-endpoint.com",
    "token": "new-token",
    "batch_size": 15
  }'

# 执行工具
curl -X POST "http://localhost:8888/api/tools/execute" \
  -H "Authorization: Bearer your-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_context",
    "arguments": {
      "project_root_path": "/path/to/project",
      "query": "搜索查询"
    }
  }'
```

### Python httpx客户端示例
```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # 获取配置
        response = await client.get(
            "http://localhost:8888/api/config",
            headers={"Authorization": "Bearer your-token-here"}
        )
        print(response.json())
        
        # 更新配置
        response = await client.post(
            "http://localhost:8888/api/config",
            headers={"Authorization": "Bearer your-token-here"},
            json={
                "base_url": "https://new-api-endpoint.com",
                "token": "new-token",
                "batch_size": 15
            }
        )
        print(response.json())
        
        # 执行工具
        response = await client.post(
            "http://localhost:8888/api/tools/execute",
            headers={"Authorization": "Bearer your-token-here"},
            json={
                "tool_name": "search_context",
                "arguments": {
                    "project_root_path": "/path/to/project",
                    "query": "搜索查询"
                }
            }
        )
        print(response.json())

asyncio.run(main())
```