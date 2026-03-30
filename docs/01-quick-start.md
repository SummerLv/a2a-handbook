# A2A 协议 5 分钟快速上手

> 最小化步骤，最快速度体验 A2A 协议

## 前置要求

- curl 或 HTTP 客户端
- Python 3.8+ (可选，用于运行示例代码)

## 第一步：发现 Agent (30秒)

每个 A2A Agent 都有一个标准化的"名片"——Agent Card。

```bash
# 获取公开示例 Agent 的信息
curl -s https://hello-world-gxfr.onrender.com/.well-known/agent.json | jq
```

**响应示例**：
```json
{
  "name": "Hello World Agent",
  "description": "A simple A2A agent for testing",
  "capabilities": {
    "streaming": true
  },
  "url": "https://hello-world-gxfr.onrender.com/"
}
```

🎉 **恭喜！你刚刚完成了 A2A 的能力发现。**

---

## 第二步：发送第一条消息 (1分钟)

使用 JSON-RPC 2.0 格式发送消息：

```bash
curl -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello, A2A!"}],
        "messageId": "msg-001"
      }
    }
  }'
```

**响应示例**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": {"state": "completed"},
    "artifacts": [
      {"parts": [{"kind": "text", "text": "Hello! Nice to meet you via A2A protocol!"}]}
    ]
  }
}
```

🎉 **你刚刚完成了第一次 A2A 通信！**

---

## 第三步：多轮对话 (1分钟)

使用 `contextId` 保持对话上下文：

```bash
# 第一次请求，获取 contextId
RESPONSE=$(curl -s -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "我叫小明"}],
        "messageId": "msg-001"
      }
    }
  }')

# 提取 contextId
CONTEXT_ID=$(echo $RESPONSE | jq -r '.result.contextId')
echo "Context ID: $CONTEXT_ID"

# 第二次请求，使用相同的 contextId
curl -s -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 2,
    \"method\": \"message/send\",
    \"params\": {
      \"message\": {
        \"role\": \"user\",
        \"parts\": [{\"kind\": \"text\", \"text\": \"你还记得我叫什么吗？\"}],
        \"messageId\": \"msg-002\",
        \"contextId\": \"$CONTEXT_ID\"
      }
    }
  }" | jq
```

---

## 第四步：流式响应 (1分钟)

对于长时间任务，使用 `message/stream` 获取实时更新：

```bash
curl -N -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/stream",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "讲一个长故事"}],
        "messageId": "msg-003"
      }
    }
  }'
```

**输出** (SSE 格式)：
```
data: {"result": {"kind": "artifact-update", "artifact": {"parts": [{"text": "从前有..."}]}}}
data: {"result": {"kind": "artifact-update", "artifact": {"parts": [{"text": "一个美丽的村庄..."}]}}}
data: {"result": {"kind": "status-update", "status": {"state": "completed"}}}
```

---

## 第五步：文件传输 (1分钟)

发送文件给 Agent：

```bash
# 准备文件内容 (base64 编码)
FILE_CONTENT=$(echo "Hello from a file!" | base64)

curl -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 1,
    \"method\": \"message/send\",
    \"params\": {
      \"message\": {
        \"role\": \"user\",
        \"parts\": [{
          \"kind\": \"file\",
          \"file\": {
            \"name\": \"hello.txt\",
            \"mimeType\": \"text/plain\",
            \"bytes\": \"$FILE_CONTENT\"
          }
        }],
        \"messageId\": \"msg-004\"
      }
    }
  }" | jq
```

---

## 常见操作速查

### 发送文本消息

```bash
curl -X POST $AGENT_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"你好"}],"messageId":"msg-001"}}}'
```

### 发送结构化数据

```bash
curl -X POST $AGENT_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"data","data":{"action":"search","query":"A2A protocol"}}],"messageId":"msg-001"}}}'
```

### 查询任务状态

```bash
curl -X POST $AGENT_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tasks/get","params":{"id":"task-uuid"}}'
```

### 取消任务

```bash
curl -X POST $AGENT_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tasks/cancel","params":{"id":"task-uuid"}}'
```

---

## Python 快速示例

```python
import requests
import uuid

class A2AClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.context_id = None
    
    def get_agent_card(self):
        """获取 Agent Card"""
        resp = requests.get(f"{self.base_url}/.well-known/agent.json")
        return resp.json()
    
    def send_message(self, text, stream=False):
        """发送消息"""
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": f"msg-{uuid.uuid4()}"
        }
        
        if self.context_id:
            message["contextId"] = self.context_id
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/stream" if stream else "message/send",
            "params": {"message": message}
        }
        
        resp = requests.post(self.base_url + "/", json=payload)
        result = resp.json().get("result", {})
        
        # 保存 contextId 用于多轮对话
        if "contextId" in result:
            self.context_id = result["contextId"]
        
        return result

# 使用示例
if __name__ == "__main__":
    client = A2AClient("https://hello-world-gxfr.onrender.com")
    
    # 获取 Agent 信息
    card = client.get_agent_card()
    print(f"Agent: {card['name']}")
    
    # 发送消息
    result = client.send_message("你好！")
    print(f"响应: {result}")
    
    # 多轮对话
    result = client.send_message("你还记得我刚才说了什么吗？")
    print(f"多轮响应: {result}")
```

---

## 下一步

- 📖 [核心概念](02-core-concepts.md) - 深入理解 A2A 协议
- 💡 [代码示例](03-examples.md) - 更多实战代码
- 🚀 [进阶主题](04-advanced.md) - 认证、安全、生产部署

## 故障排除

### 请求失败：404

确保 URL 正确：
- Agent Card: `/.well-known/agent.json`
- 消息端点: `/` (根据 Agent Card 中的 `url`)

### 请求失败：415

确保请求头包含：
```bash
-H "Content-Type: application/json"
```

### 多轮对话不工作

确保每次请求都带上正确的 `contextId`。

### 流式响应不更新

确保使用 `curl -N` 参数（禁用缓冲）或支持 SSE 的客户端。
