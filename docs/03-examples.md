# A2A 协议代码示例

本文档提供 A2A 协议的各种实现示例。

## 目录

1. [Python 服务端](#python-服务端)
2. [Python 客户端](#python-客户端)
3. [cURL 示例](#curl-示例)
4. [多轮对话](#多轮对话)
5. [文件传输](#文件传输)
6. [流式响应](#流式响应)

---

## Python 服务端

### 最小化服务端

```python
#!/usr/bin/env python3
"""最小化 A2A 服务端"""

import json
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

AGENT_CARD = {
    "name": "Simple Agent",
    "description": "最小化 A2A 服务",
    "version": "1.0.0",
    "capabilities": {"streaming": False},
    "skills": [{
        "id": "echo",
        "name": "Echo",
        "description": "返回用户输入"
    }],
    "url": "http://127.0.0.1:8888/"
}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/.well-known/agent.json':
            self.send_json(AGENT_CARD)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if body.get('method') == 'message/send':
            parts = body['params']['message']['parts']
            text = next(p['text'] for p in parts if p['kind'] == 'text')
            self.send_json({
                "jsonrpc": "2.0",
                "id": body['id'],
                "result": {
                    "kind": "message",
                    "messageId": str(uuid.uuid4()),
                    "parts": [{"kind": "text", "text": f"Echo: {text}"}],
                    "role": "agent"
                }
            })

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8888), Handler)
    print("Server running at http://127.0.0.1:8888/")
    server.serve_forever()
```

### 完整功能服务端

参考 [scripts/full_server.py](../.agents/skills/a2a-handbook/scripts/full_server.py)

---

## Python 客户端

### 基础客户端

```python
#!/usr/bin/env python3
"""A2A 客户端"""

import requests
import uuid

class A2AClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
    
    def get_agent_card(self):
        """获取 Agent Card"""
        resp = requests.get(f"{self.base_url}/.well-known/agent.json")
        return resp.json()
    
    def send_message(self, text, context_id=None, task_id=None):
        """发送消息"""
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": str(uuid.uuid4())
        }
        if context_id:
            message["contextId"] = context_id
        if task_id:
            message["taskId"] = task_id
        
        resp = requests.post(self.base_url, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": message}
        })
        return resp.json()

# 使用示例
if __name__ == '__main__':
    client = A2AClient("http://127.0.0.1:8888")
    
    # 获取 Agent Card
    card = client.get_agent_card()
    print(f"Agent: {card['name']}")
    
    # 发送消息
    result = client.send_message("你好!")
    print(f"响应: {result['result']['parts'][0]['text']}")
```

---

## cURL 示例

### 获取 Agent Card

```bash
curl http://127.0.0.1:8888/.well-known/agent.json
```

### 发送消息

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
        "parts": [{"kind": "text", "text": "hello"}],
        "messageId": "test-001"
      }
    }
  }'
```

### 使用 jq 格式化输出

```bash
curl -s http://127.0.0.1:8888/.well-known/agent.json | jq .
```

---

## 多轮对话

```python
def multi_turn_conversation():
    client = A2AClient("http://127.0.0.1:8888")
    
    # 第一轮
    result1 = client.send_message("我想预订机票")
    context_id = result1['result'].get('contextId')
    print(f"第一轮: {result1['result']['parts'][0]['text']}")
    
    # 第二轮 (使用相同 contextId)
    result2 = client.send_message("北京到上海", context_id=context_id)
    print(f"第二轮: {result2['result']['parts'][0]['text']}")
```

---

## 文件传输

### 发送文件

```python
import base64

def send_file(client, file_path):
    # 读取文件
    with open(file_path, 'rb') as f:
        file_bytes = base64.b64encode(f.read()).decode()
    
    message = {
        "role": "user",
        "parts": [
            {"kind": "text", "text": "请处理这个文件"},
            {
                "kind": "file",
                "file": {
                    "name": "document.pdf",
                    "mimeType": "application/pdf",
                    "bytes": file_bytes
                }
            }
        ],
        "messageId": str(uuid.uuid4())
    }
    
    resp = requests.post(client.base_url, json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": message}
    })
    return resp.json()
```

### 接收文件

响应中的文件通过 URI 或 bytes 提供：

```json
{
  "result": {
    "parts": [{
      "kind": "file",
      "file": {
        "name": "output.pdf",
        "mimeType": "application/pdf",
        "uri": "https://storage.example.com/output.pdf?token=xxx"
      }
    }]
  }
}
```

---

## 流式响应

### 使用 SSE

```python
import sseclient

def stream_message(client, text):
    message = {
        "role": "user",
        "parts": [{"kind": "text", "text": text}],
        "messageId": str(uuid.uuid4())
    }
    
    resp = requests.post(
        client.base_url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/stream",
            "params": {"message": message}
        },
        stream=True
    )
    
    full_text = ""
    for line in resp.iter_lines():
        if line and line.startswith(b'data: '):
            data = json.loads(line[6:])
            if data.get('result', {}).get('kind') == 'artifact-update':
                for part in data['result']['artifact']['parts']:
                    if 'text' in part:
                        print(part['text'], end='', flush=True)
                        full_text += part['text']
    
    return full_text
```

---

## 完整示例脚本

参考 [scripts/test_a2a.sh](../.agents/skills/a2a-handbook/scripts/test_a2a.sh)
