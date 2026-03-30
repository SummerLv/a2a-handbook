#!/usr/bin/env python3
"""
最小化 A2A 服务端 - 用于快速演示和测试
启动: python3 simple_server.py
测试: curl http://127.0.0.1:8888/.well-known/agent.json
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import uuid

AGENT_CARD = {
    "name": "Simple A2A Agent",
    "description": "最小化 A2A 协议演示服务",
    "version": "1.0.0",
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [{
        "id": "echo",
        "name": "Echo",
        "description": "返回用户输入",
        "tags": ["echo", "test"],
        "examples": ["hello", "test"]
    }],
    "url": "http://127.0.0.1:8888/"
}

class A2AHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.command}] {args[0]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        print(f"\n{'='*50}")
        print(f"📥 GET {self.path}")
        print(f"{'='*50}")
        
        if self.path == '/.well-known/agent.json':
            print("📋 返回 Agent Card")
            self.send_json(AGENT_CARD)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        print(f"\n{'='*50}")
        print(f"📤 POST {self.path}")
        print(f"{'='*50}")
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            request = json.loads(body)
        except:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        
        print(f"📨 Request:\n{json.dumps(request, indent=2, ensure_ascii=False)}")
        
        if self.path == '/':
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'message/send':
                message = params.get('message', {})
                parts = message.get('parts', [])
                user_text = ''
                for part in parts:
                    if part.get('kind') == 'text':
                        user_text = part.get('text', '')
                
                print(f"💬 用户消息: {user_text}")
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get('id'),
                    "result": {
                        "kind": "message",
                        "messageId": str(uuid.uuid4()),
                        "parts": [{"kind": "text", "text": f"Echo: {user_text}"}],
                        "role": "agent"
                    }
                }
                print(f"📨 Response:\n{json.dumps(response, indent=2, ensure_ascii=False)}")
                self.send_json(response)
            else:
                self.send_json({
                    "jsonrpc": "2.0",
                    "id": request.get('id'),
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })
        else:
            self.send_json({"error": "Not found"}, 404)

if __name__ == '__main__':
    HOST, PORT = '127.0.0.1', 8888
    server = HTTPServer((HOST, PORT), A2AHandler)
    print(f"🚀 A2A Server running at http://{HOST}:{PORT}/")
    print(f"📋 Agent Card: http://{HOST}:{PORT}/.well-known/agent.json")
    print("="*50)
    server.serve_forever()
