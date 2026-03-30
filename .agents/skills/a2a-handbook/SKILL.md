---
name: a2a-handbook
description: A2A (Agent-to-Agent) 协议学习和实践指南。使用场景：(1) 用户想了解 A2A 协议 (2) 用户需要实现 A2A 服务端或客户端 (3) 用户需要调试 A2A 通信 (4) 用户想快速上手 A2A 开发。触发词：A2A, a2a, Agent-to-Agent, agent 协议, 多 agent 通信。
---

# A2A Handbook

交互式 A2A 协议学习和实践指南。

## 可用 Skills

本项目包含多个子 skill：

| Skill | 说明 |
|-------|------|
| `/a2a-learn` | 学习模式 - 了解 A2A 协议概念和规范 |
| `/a2a-practice` | 实践模式 - 启动本地服务并抓包 |
| `/a2a-debug` | 调试模式 - 分析 A2A 通信流量 |
| `/a2a-build` | 构建模式 - 生成 A2A 服务端/客户端代码 |

## 快速开始

### 学习 A2A 基础

```
/a2a-learn
```

回答关于 A2A 的问题，解释核心概念。

### 启动本地服务

```
/a2a-practice
```

启动一个最小化的 A2A 服务端，并提供抓包演示。

### 调试 A2A 流量

```
/a2a-debug <url>
```

分析指定 A2A 服务的通信流程。

### 生成代码

```
/a2a-build server --lang python
/a2a-build client --lang python
```

生成 A2A 服务端或客户端模板代码。

## 核心概念速查

### Agent Card 端点

```
GET /.well-known/agent.json
```

### JSON-RPC 方法

| 方法 | 说明 |
|------|------|
| `message/send` | 发送消息，同步响应 |
| `message/stream` | 发送消息，SSE 流式响应 |
| `tasks/get` | 查询任务状态 |
| `tasks/cancel` | 取消任务 |

### 消息结构

```json
{
  "role": "user",
  "parts": [{"kind": "text", "text": "..."}],
  "messageId": "uuid"
}
```

### Part 类型

| kind | 说明 |
|------|------|
| `text` | 文本内容 |
| `file` | 文件（base64 或 URI） |
| `data` | 结构化数据 |

### Task 状态

```
submitted → working → completed
                  ↘ input-required
                  ↘ cancelled
```

## 参考资源

- [skills/learn/SKILL.md](skills/learn/SKILL.md) - 学习模式详细说明
- [skills/practice/SKILL.md](skills/practice/SKILL.md) - 实践模式详细说明
- [scripts/](scripts/) - 辅助脚本
