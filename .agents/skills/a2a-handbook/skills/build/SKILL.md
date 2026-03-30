---
name: a2a-build
description: A2A 代码生成器。生成 A2A 服务端或客户端代码模板。触发词：生成 A2A 代码, A2A 服务端, A2A 客户端, build A2A。
---

# A2A 构建模式

生成 A2A 服务端和客户端代码模板。

## 使用方法

```
/a2a-build server --lang python
/a2a-build client --lang python
```

## Python 服务端模板

```python
#!/usr/bin/env python3
"""A2A 服务端模板"""

import json
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

AGENT_CARD = {
    "name": "Your Agent",
    "description": "Agent 描述",
    "version": "1.0.0",
    "capabilities": {"streaming": False},
    "skills": [],
    "url": "http://127.0.0.1:8888/"
}

class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/.well-known/agent.json':
            self.send_json(AGENT_CARD)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if body.get('method') == 'message/send':
            parts = body['params']['message']['parts']
            text = next((p['text'] for p in parts if p['kind'] == 'text'), '')
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

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8888), Handler)
    print("Server: http://127.0.0.1:8888/")
    server.serve_forever()
```

## Python 客户端模板

```python
#!/usr/bin/env python3
import requests
import uuid

class A2AClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
    
    def get_agent_card(self):
        return requests.get(f"{self.base_url}/.well-known/agent.json").json()
    
    def send_message(self, text, context_id=None):
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": str(uuid.uuid4())
        }
        if context_id:
            message["contextId"] = context_id
        return requests.post(self.base_url, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "message/send",
            "params": {"message": message}
        }).json()

# 使用
client = A2AClient("http://127.0.0.1:8888")
print(client.get_agent_card())
print(client.send_message("hello"))
```

完整模板见 [scripts/](scripts/) 目录。
