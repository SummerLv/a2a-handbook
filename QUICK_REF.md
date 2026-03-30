# A2A Handbook - 快速参考卡

## 🔗 核心端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/.well-known/agent.json` | GET | Agent Card |
| `/` | POST | JSON-RPC 入口 |

## 📨 JSON-RPC 方法

| 方法 | 说明 | 使用场景 |
|------|------|---------|
| `message/send` | 同步消息 | 简单查询 |
| `message/stream` | 流式消息 | 长响应 |
| `tasks/get` | 查询任务 | 异步任务 |
| `tasks/cancel` | 取消任务 | 终止任务 |

## 📋 Part 类型

| kind | 用途 | 示例 |
|------|------|------|
| `text` | 文本 | `{"kind":"text","text":"hello"}` |
| `file` | 文件 | `{"kind":"file","file":{"name":"...","bytes":"..."}}` |
| `data` | 数据 | `{"kind":"data","data":{...}}` |

## 🔄 Task 状态

```
submitted → working → completed
                 ↘ input-required
                 ↘ cancelled
```

## ❌ 错误码

| 码 | 说明 |
|----|------|
| -32700 | JSON 解析错误 |
| -32600 | 无效请求 |
| -32601 | 方法不存在 |
| -32602 | 参数无效 |
| -32603 | 内部错误 |
| -32001 | Task 不存在 |

## 🔐 认证

```bash
# Bearer Token
curl -H "Authorization: Bearer YOUR_TOKEN" ...

# API Key
curl -H "X-API-Key: YOUR_KEY" ...
```

## 🛠️ 常用命令

```bash
# 获取 Agent Card
curl https://agent.example.com/.well-known/agent.json | jq .

# 发送消息
curl -X POST https://agent.example.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"hello"}],"messageId":"test"}}}'

# 测试服务
python3 examples/python/test_client.py http://127.0.0.1:8888 --test all
```

## 📚 文档索引

| 文档 | 内容 |
|------|------|
| [01-quick-start.md](docs/01-quick-start.md) | 5分钟上手 |
| [02-core-concepts.md](docs/02-core-concepts.md) | 核心概念 |
| [05-scenarios.md](docs/05-scenarios.md) | 场景全景 |
| [06-security-guide.md](docs/06-security-guide.md) | 安全指南 |
| [08-troubleshooting.md](docs/08-troubleshooting.md) | 故障排查 |

## 🔗 外部资源

- [官方规范](https://a2a-protocol.org/)
- [GitHub](https://github.com/a2aproject/A2A)
- [A2A Registry](https://a2aregistry.in/)
