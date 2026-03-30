# A2A 协议规范参考

> 完整的 JSON Schema 定义和 API 参考

## 目录

1. [Agent Card Schema](#agent-card-schema)
2. [Message Schema](#message-schema)
3. [Part Schema](#part-schema)
4. [Task Schema](#task-schema)
5. [JSON-RPC 方法](#json-rpc-方法)
6. [错误码定义](#错误码定义)

---

## Agent Card Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentCard",
  "type": "object",
  "required": ["name", "url"],
  "properties": {
    "name": {
      "type": "string",
      "description": "Agent 名称",
      "example": "Travel Agent"
    },
    "description": {
      "type": "string",
      "description": "Agent 功能描述",
      "example": "帮助用户预订机票和酒店"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "版本号，遵循语义化版本",
      "example": "1.0.0"
    },
    "capabilities": {
      "type": "object",
      "properties": {
        "streaming": {
          "type": "boolean",
          "default": false,
          "description": "是否支持 SSE 流式响应"
        },
        "push_notifications": {
          "type": "boolean",
          "default": false,
          "description": "是否支持 Webhook 推送"
        },
        "extended_agent_card": {
          "type": "boolean",
          "default": false,
          "description": "是否支持认证后的扩展 Agent Card"
        }
      }
    },
    "defaultInputModes": {
      "type": "array",
      "items": {"type": "string"},
      "description": "默认输入类型",
      "example": ["text", "application/json"]
    },
    "defaultOutputModes": {
      "type": "array",
      "items": {"type": "string"},
      "description": "默认输出类型",
      "example": ["text", "application/json"]
    },
    "skills": {
      "type": "array",
      "items": {"$ref": "#/definitions/Skill"},
      "description": "Agent 提供的技能列表"
    },
    "supported_interfaces": {
      "type": "array",
      "items": {"$ref": "#/definitions/AgentInterface"},
      "description": "支持的连接方式"
    },
    "securitySchemes": {
      "type": "object",
      "additionalProperties": {"$ref": "#/definitions/SecurityScheme"},
      "description": "认证方案定义"
    },
    "url": {
      "type": "string",
      "format": "uri",
      "description": "Agent 的基础 URL"
    }
  },
  "definitions": {
    "Skill": {
      "type": "object",
      "required": ["id", "name"],
      "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "tags": {
          "type": "array",
          "items": {"type": "string"}
        },
        "examples": {
          "type": "array",
          "items": {"type": "string"}
        },
        "input_modes": {
          "type": "array",
          "items": {"type": "string"}
        },
        "output_modes": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "AgentInterface": {
      "type": "object",
      "properties": {
        "protocol_binding": {
          "type": "string",
          "enum": ["JSONRPC", "REST", "GRPC"],
          "default": "JSONRPC"
        },
        "url": {
          "type": "string",
          "format": "uri"
        }
      }
    },
    "SecurityScheme": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["http", "oauth2", "apiKey"]
        },
        "scheme": {"type": "string"},
        "description": {"type": "string"}
      }
    }
  }
}
```

**示例**：
```json
{
  "name": "Travel Agent",
  "description": "帮助用户预订机票和酒店",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "push_notifications": true,
    "extended_agent_card": false
  },
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  "skills": [
    {
      "id": "book_flight",
      "name": "预订机票",
      "description": "搜索并预订机票",
      "tags": ["flight", "booking"],
      "examples": ["帮我订一张北京到上海的机票"]
    }
  ],
  "url": "https://travel-agent.example.com/"
}
```

---

## Message Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Message",
  "type": "object",
  "required": ["role", "parts", "messageId"],
  "properties": {
    "role": {
      "type": "string",
      "enum": ["user", "agent"],
      "description": "消息角色"
    },
    "parts": {
      "type": "array",
      "items": {"$ref": "#/definitions/Part"},
      "description": "消息内容部分"
    },
    "messageId": {
      "type": "string",
      "format": "uuid",
      "description": "消息唯一标识"
    },
    "contextId": {
      "type": "string",
      "format": "uuid",
      "description": "会话上下文 ID（多轮对话时使用）"
    },
    "taskId": {
      "type": "string",
      "format": "uuid",
      "description": "关联的任务 ID"
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "description": "可选的元数据"
    }
  }
}
```

---

## Part Schema

### TextPart

```json
{
  "kind": "text",
  "text": "这是文本内容"
}
```

### FilePart

```json
{
  "kind": "file",
  "file": {
    "name": "document.pdf",
    "mimeType": "application/pdf",
    "bytes": "JVBERi0xLjQK..."  // base64 编码
    // 或使用 URI
    // "uri": "https://storage.example.com/file.pdf"
  }
}
```

### DataPart

```json
{
  "kind": "data",
  "data": {
    "type": "object",
    "properties": {
      "key": {"type": "string"}
    }
  }
}
```

---

## Task Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Task",
  "type": "object",
  "required": ["id", "status"],
  "properties": {
    "id": {
      "type": "string",
      "description": "任务唯一标识"
    },
    "contextId": {
      "type": "string",
      "description": "关联的上下文 ID"
    },
    "status": {
      "type": "object",
      "required": ["state"],
      "properties": {
        "state": {
          "type": "string",
          "enum": ["submitted", "working", "input-required", "completed", "cancelled"],
          "description": "任务状态"
        },
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "description": "状态更新时间"
        },
        "message": {
          "$ref": "#/definitions/Message",
          "description": "状态相关的消息（如 input-required 时的提示）"
        }
      }
    },
    "history": {
      "type": "array",
      "items": {"$ref": "#/definitions/Message"},
      "description": "消息历史"
    },
    "artifacts": {
      "type": "array",
      "items": {"$ref": "#/definitions/Artifact"},
      "description": "生成的产物"
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true
    }
  },
  "definitions": {
    "Artifact": {
      "type": "object",
      "required": ["artifactId", "parts"],
      "properties": {
        "artifactId": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "parts": {
          "type": "array",
          "items": {"$ref": "Part"}
        }
      }
    }
  }
}
```

### 任务状态流转

```
┌────────────┐
│ submitted  │
└─────┬──────┘
      │
      ▼
┌────────────┐
│  working   │◄────────┐
└─────┬──────┘         │
      │                │
      ├──► completed   │
      │                │
      ├──► input-required ──┘
      │      (用户提供更多输入后返回 working)
      │
      └──► cancelled
```

---

## JSON-RPC 方法

### message/send

发送消息，同步响应。

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "hello"}],
      "messageId": "uuid-here"
    },
    "metadata": {}
  }
}
```

**响应（直接消息）**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "kind": "message",
    "messageId": "agent-msg-uuid",
    "contextId": "ctx-uuid",
    "parts": [{"kind": "text", "text": "Hello!"}],
    "role": "agent"
  }
}
```

**响应（任务）**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "id": "task-uuid",
    "contextId": "ctx-uuid",
    "status": {"state": "input-required"},
    "history": [...],
    "kind": "task"
  }
}
```

### message/stream

发送消息，SSE 流式响应。

**请求**：同 `message/send`，但 method 为 `message/stream`

**响应**（SSE 格式）：
```
data: {"jsonrpc":"2.0","result":{"kind":"artifact-update","taskId":"...","artifact":{...}}}

data: {"jsonrpc":"2.0","result":{"kind":"status-update","taskId":"...","status":{"state":"completed"}}}
```

### tasks/get

查询任务状态。

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tasks/get",
  "params": {
    "id": "task-uuid"
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "id": "task-uuid",
    "status": {"state": "completed"},
    "artifacts": [...],
    "kind": "task"
  }
}
```

### tasks/cancel

取消任务。

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tasks/cancel",
  "params": {
    "id": "task-uuid"
  }
}
```

### tasks/pushNotificationConfig

配置 Webhook 推送通知。

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tasks/pushNotificationConfig",
  "params": {
    "id": "task-uuid",
    "pushNotificationConfig": {
      "url": "https://client.example.com/webhook",
      "token": "secure-token"
    }
  }
}
```

---

## 错误码定义

| 错误码 | 名称 | 说明 |
|--------|------|------|
| -32700 | Parse error | JSON 解析错误 |
| -32600 | Invalid Request | 无效的 JSON-RPC 请求 |
| -32601 | Method not found | 方法不存在 |
| -32602 | Invalid params | 无效的参数 |
| -32603 | Internal error | 内部错误 |
| -32001 | Task not found | 任务不存在 |
| -32002 | Task not cancelable | 任务无法取消 |
| -32003 | Push notification not supported | 不支持推送通知 |
| -32004 | Unsupported operation | 不支持的操作 |
| -32005 | ContentType not supported | 不支持的内容类型 |

**错误响应示例**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "field": "message.parts",
      "reason": "parts array cannot be empty"
    }
  }
}
```

---

## 完整示例流程

### 多轮对话示例

```
Client                          Agent
  │                               │
  │  POST / (message/send)        │
  │  {"parts":[{"text":"你好"}]}  │
  │──────────────────────────────▶│
  │                               │
  │  {"result": {                 │
  │    "contextId": "ctx-123",    │
  │    "parts":[{"text":"你好！"}]│
  │  }}                           │
  │◀──────────────────────────────│
  │                               │
  │  POST / (message/send)        │
  │  {"contextId":"ctx-123",      │
  │   "parts":[{"text":"继续"}]}  │
  │──────────────────────────────▶│
  │                               │
  │  {"result": {                 │
  │    "contextId": "ctx-123",    │
  │    "parts":[{"text":"..."}]   │
  │  }}                           │
  │◀──────────────────────────────│
```
