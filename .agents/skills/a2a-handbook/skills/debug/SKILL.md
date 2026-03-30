---
name: a2a-debug
description: A2A 协议调试模式。分析 A2A 服务的通信流量和问题。触发词：调试 A2A, A2A debug, A2A 问题, A2A 抓包分析。
---

# A2A 调试模式

帮助分析和调试 A2A 通信问题。

## 使用方法

```
/a2a-debug <agent_url>
```

## 调试流程

### 1. 检查 Agent Card

首先验证 Agent Card 是否正确：

```bash
# 获取 Agent Card
curl -v https://agent.example.com/.well-known/agent.json

# 检查关键字段
curl -s https://agent.example.com/.well-known/agent.json | jq '{name, skills, capabilities, url}'
```

**检查项**：
- ✅ `name` 和 `description` 是否正确
- ✅ `skills` 是否包含预期技能
- ✅ `url` 是否与实际地址一致
- ✅ `capabilities` 是否声明正确

### 2. 测试 JSON-RPC 连接

发送测试请求：

```bash
curl -v -X POST https://agent.example.com/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "test"}],
        "messageId": "debug-001"
      }
    }
  }'
```

**检查项**：
- ✅ HTTP 状态码应为 200
- ✅ Content-Type 应为 `application/json`
- ✅ 响应应包含 `jsonrpc: "2.0"`
- ✅ `id` 应与请求一致

### 3. 分析错误响应

**常见错误**：

| 错误码 | 说明 | 解决方案 |
|--------|------|---------|
| -32700 | JSON 解析错误 | 检查请求格式 |
| -32600 | 无效请求 | 检查 JSON-RPC 格式 |
| -32601 | 方法不存在 | 检查 method 名称 |
| -32602 | 无效参数 | 检查 params 结构 |
| -32603 | 内部错误 | 查看服务端日志 |

### 4. 抓包分析

使用 tcpdump：

```bash
# 抓取 HTTP 流量
tcpdump -i any -w a2a.pcap host agent.example.com and port 443

# 分析
tshark -r a2a.pcap -Y "http" -T json
```

使用 mitmproxy：

```bash
# 代理模式
mitmproxy --mode reverse:https://agent.example.com -p 8080

# 然后请求 http://localhost:8080
```

### 5. 日志分析

服务端应记录：
- 请求时间戳
- 请求方法和参数
- 响应时间和结果
- 错误堆栈（如果有）

## 常见问题

### 问题 1: Agent Card 返回 404

**原因**：
- 端点路径错误
- 服务未启动
- 路由配置错误

**解决**：
```bash
# 检查服务是否运行
curl -v https://agent.example.com/

# 检查其他路径
curl https://agent.example.com/agent.json
curl https://agent.example.com/.well-known/agent-card.json
```

### 问题 2: JSON-RPC 请求失败

**检查请求格式**：
```bash
# 验证 JSON 格式
echo '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "test"}],
      "messageId": "test-001"
    }
  }
}' | jq .
```

### 问题 3: 多轮对话上下文丢失

**检查 contextId**：

```python
# 确保每次请求携带相同的 contextId
def debug_context():
    resp1 = send_message("第一轮")
    context_id = resp1['result'].get('contextId')
    print(f"ContextId: {context_id}")
    
    # 第二轮必须使用相同的 contextId
    resp2 = send_message("第二轮", context_id=context_id)
    print(f"ContextId in response: {resp2['result'].get('contextId')}")
```

### 问题 4: SSE 流无响应

**检查**：
- Content-Type 是否为 `text/event-stream`
- 是否有 `data:` 前缀
- 连接是否保持

```bash
curl -N -X POST https://agent.example.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/stream","params":{...}}'
```

### 问题 5: 文件传输失败

**检查**：
- 文件大小限制
- base64 编码是否正确
- mimeType 是否正确

```python
import base64

# 正确编码
with open('file.pdf', 'rb') as f:
    encoded = base64.b64encode(f.read()).decode()

# 正确解码
decoded = base64.b64decode(encoded)
```

## 调试工具

### curl -v

查看完整的请求和响应头：

```bash
curl -v -X POST https://agent.example.com/ \
  -H "Content-Type: application/json" \
  -d @request.json
```

### jq

格式化和过滤 JSON：

```bash
# 格式化
curl -s ... | jq .

# 提取特定字段
curl -s ... | jq '.result.parts[0].text'

# 过滤错误
curl -s ... | jq 'select(.error) | .error.message'
```

### httpie

更友好的 HTTP 客户端：

```bash
# 安装
pip install httpie

# 使用
http POST https://agent.example.com/ jsonrpc=2.0 id=1 method=message/send params:='{"message": {...}}'
```

## 性能分析

### 响应时间

```bash
# 测量响应时间
curl -w "Time: %{time_total}s\n" -X POST https://agent.example.com/ \
  -H "Content-Type: application/json" \
  -d @request.json -o /dev/null -s
```

### 并发测试

```bash
# 使用 ab (Apache Bench)
ab -n 100 -c 10 -p request.json -T application/json https://agent.example.com/

# 使用 wrk
wrk -t 4 -c 100 -d 30s -s request.lua https://agent.example.com/
```

## 获取帮助

如果问题无法解决：
1. 查看服务端日志
2. 检查网络配置（防火墙、代理等）
3. 参考 [references/protocol-spec.md](references/protocol-spec.md)
