---
name: a2a-practice
description: A2A 协议实践模式。启动本地 A2A 服务并进行抓包演示。触发词：实践 A2A, A2A 演示, A2A demo, 启动 A2A 服务, A2A 抓包。
---

# A2A 实践模式

启动本地 A2A 服务并进行交互演示。

## 快速启动

### 1. 启动最小化服务

```bash
python3 scripts/simple_server.py
```

服务将在 `http://127.0.0.1:8888` 启动。

### 2. 获取 Agent Card

```bash
curl http://127.0.0.1:8888/.well-known/agent.json | jq .
```

### 3. 发送消息

```bash
curl -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "你好"}],
        "messageId": "test-001"
      }
    }
  }' | jq .
```

## 测试场景

### 场景 1: 简单消息

```bash
curl -s -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"hello"}],"messageId":"m1"}}}' | jq .result
```

### 场景 2: 多轮对话

```bash
# 第一轮
RESP1=$(curl -s -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"第一轮"}],"messageId":"m1"}}}')
CTX=$(echo "$RESP1" | jq -r '.result.contextId')
echo "ContextId: $CTX"

# 第二轮 (使用相同 contextId)
curl -s -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"parts\":[{\"kind\":\"text\",\"text\":\"第二轮\"}],\"messageId\":\"m2\",\"contextId\":\"$CTX\"}}}" | jq .result
```

### 场景 3: 文件上传

```bash
curl -s -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {"kind": "text", "text": "处理这个文件"},
          {"kind": "file", "file": {"name": "test.txt", "mimeType": "text/plain", "bytes": "dGVzdA=="}}
        ],
        "messageId": "m1"
      }
    }
  }' | jq .result
```

### 场景 4: 流式响应

```bash
curl -s -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/stream","params":{"message":{"role":"user","parts":[{"kind":"text","text":"写一段话"}],"messageId":"m1"}}}'
```

## 公开测试服务

可以使用以下公开的 A2A 服务进行测试：

**Hello World Agent**
- URL: `https://hello-world-gxfr.onrender.com/`
- Agent Card: `https://hello-world-gxfr.onrender.com/.well-known/agent.json`

```bash
# 获取 Agent Card
curl https://hello-world-gxfr.onrender.com/.well-known/agent.json | jq .

# 发送消息
curl -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"hello"}],"messageId":"test"}}}' | jq .
```

## 抓包分析

### 使用 curl -v

```bash
curl -v -X POST http://127.0.0.1:8888/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"test"}],"messageId":"m1"}}}'
```

### 使用 tcpdump

```bash
# 抓包
tcpdump -i lo -w a2a.pcap port 8888

# 分析
tshark -r a2a.pcap -Y "http" -T json
```

### 使用 mitmproxy

```bash
mitmproxy --mode reverse:http://127.0.0.1:8888 -p 8080
# 然后让请求发送到 8080
```

## 服务端代码参考

参考 [scripts/simple_server.py](scripts/simple_server.py) 和 [scripts/full_server.py](scripts/full_server.py)。
