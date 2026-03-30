---
name: a2a-learn
description: A2A 协议学习模式。用于学习 A2A 协议的核心概念、规范和最佳实践。触发词：学习 A2A, A2A 教程, A2A 是什么, A2A 概念。
---

# A2A 学习模式

帮助开发者快速理解 A2A 协议。

## 学习路径

### 1. 基础概念

A2A (Agent-to-Agent) 是一个开放协议，让不同 AI Agent 能够互相发现、通信和协作。

**核心问题**：不同团队、不同框架开发的 Agent 如何互操作？

**解决方案**：
- 标准化的能力发现 (Agent Card)
- 标准化的通信协议 (JSON-RPC over HTTP)
- 标准化的任务管理 (Task 生命周期)

### 2. Agent Card (能力发现)

Agent Card 是 Agent 的"数字名片"，告诉其他 Agent：
- 我是谁 (name, description)
- 我能做什么 (skills)
- 怎么联系我 (url, supported_interfaces)
- 需要什么认证 (securitySchemes)

**端点**: `GET /.well-known/agent.json`

**示例**:
```json
{
  "name": "Travel Agent",
  "description": "帮用户预订机票、酒店",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "push_notifications": true
  },
  "skills": [{
    "id": "book_flight",
    "name": "预订机票",
    "description": "搜索并预订机票",
    "tags": ["flight", "booking"],
    "examples": ["帮我订一张北京到上海的机票"]
  }],
  "url": "https://travel-agent.example.com/"
}
```

### 3. JSON-RPC 通信

A2A 使用 JSON-RPC 2.0 over HTTP 进行通信。

**请求结构**:
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
    }
  }
}
```

**响应结构**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "kind": "message",
    "messageId": "agent-msg-uuid",
    "parts": [{"kind": "text", "text": "Hello!"}],
    "role": "agent"
  }
}
```

### 4. 消息 Part 类型

| kind | 用途 | 结构 |
|------|------|------|
| `text` | 文本消息 | `{"kind": "text", "text": "内容"}` |
| `file` | 文件传输 | `{"kind": "file", "file": {"name": "...", "mimeType": "...", "bytes": "base64"}}` |
| `data` | 结构化数据 | `{"kind": "data", "data": {...}}` |

### 5. Task 生命周期

```
         ┌──────────────┐
         │  submitted   │
         └──────┬───────┘
                │
         ┌──────▼───────┐
         │   working    │◄────────┐
         └──────┬───────┘         │
                │                 │
    ┌───────────┼───────────┐     │
    │           │           │     │
┌───▼───┐  ┌────▼────┐  ┌───▼───┐ │
│completed│ │input-   │  │cancelled│
│         │ │required │  │         │
└─────────┘ └────┬────┘  └─────────┘
                 │
                 └─────────►(用户提供更多输入)
```

### 6. SSE 流式响应

使用 `message/stream` 方法获取流式响应：

**请求**:
```json
{
  "method": "message/stream",
  "params": {...}
}
```

**响应** (SSE 格式):
```
data: {"result": {"kind": "artifact-update", "artifact": {...}}}
data: {"result": {"kind": "artifact-update", "artifact": {...}}}
data: {"result": {"kind": "status-update", "status": {"state": "completed"}}}
```

### 7. 多轮对话

使用 `contextId` 维护会话上下文：

```json
// 第一轮
{"message": {"text": "预订机票", "messageId": "m1"}}
// 响应包含 contextId

// 第二轮 (使用相同 contextId)
{"message": {"text": "北京到上海", "messageId": "m2", "contextId": "ctx-123"}}
```

### 8. 与 MCP 的关系

| 协议 | 解决的问题 |
|------|-----------|
| **A2A** | Agent 之间的通信和协作 |
| **MCP** | Agent 与工具/数据源的连接 |

两者互补，可以组合使用。

## 常见问题

**Q: A2A 与 HTTP API 有什么区别？**

A: A2A 是专门为 AI Agent 设计的：
- 能力发现机制 (Agent Card)
- 任务生命周期管理
- 多模态内容 (Part)
- 流式响应支持
- 认证和安全设计

**Q: 如何实现认证？**

A: Agent Card 中声明 `securitySchemes`，支持：
- Bearer Token
- OAuth2
- API Key

**Q: 支持哪些编程语言？**

A: 任何支持 HTTP 的语言都可以实现。官方提供 Python SDK。

## 下一步

- 运行 `/a2a-practice` 启动本地服务
- 查看 [references/protocol-spec.md](references/protocol-spec.md) 了解完整规范
