#!/usr/bin/env python3
"""
A2A 异常处理演示
展示各种异常场景的处理方式

运行: python3 error_demo.py
"""

import json
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

class ErrorDemoHandler(BaseHTTPRequestHandler):
    """演示各种错误场景的 Handler"""
    
    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)
    
    def send_error_response(self, code: int, message: str, data: dict = None, http_status: int = 200):
        """发送 JSON-RPC 错误响应"""
        error = {"code": code, "message": message}
        if data:
            error["data"] = data
        self.send_json({
            "jsonrpc": "2.0",
            "id": getattr(self, 'request_id', None),
            "error": error
        }, http_status)
    
    def do_GET(self):
        if self.path == '/.well-known/agent.json':
            self.send_json({
                "name": "Error Demo Agent",
                "description": "演示各种错误场景",
                "version": "1.0.0",
                "skills": [{"id": "demo", "name": "Demo"}],
                "url": "http://127.0.0.1:9999/"
            })
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        
        # 错误 1: 空请求体
        if content_length == 0:
            self.send_error_response(-32700, "Parse error: empty request", http_status=400)
            return
        
        try:
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
        except json.JSONDecodeError as e:
            # 错误 2: 无效 JSON
            self.send_error_response(-32700, f"Parse error: {str(e)}", http_status=400)
            return
        
        self.request_id = request.get('id')
        
        # 错误 3: 缺少必填字段
        if 'jsonrpc' not in request:
            self.send_error_response(-32600, "Invalid Request: missing jsonrpc")
            return
        if request['jsonrpc'] != '2.0':
            self.send_error_response(-32600, "Invalid Request: unsupported jsonrpc version")
            return
        if 'method' not in request:
            self.send_error_response(-32600, "Invalid Request: missing method")
            return
        
        method = request['method']
        params = request.get('params', {})
        
        # 错误 4: 方法不存在
        if method not in ['message/send', 'message/stream', 'tasks/get', 'tasks/cancel']:
            self.send_error_response(-32601, f"Method not found: {method}")
            return
        
        # 错误 5: 参数无效
        if method == 'message/send':
            if 'message' not in params:
                self.send_error_response(-32602, "Invalid params: missing message")
                return
            
            message = params['message']
            
            # 检查 message 结构
            if 'role' not in message:
                self.send_error_response(-32602, "Invalid params: message missing role")
                return
            if 'parts' not in message:
                self.send_error_response(-32602, "Invalid params: message missing parts")
                return
            if not isinstance(message['parts'], list):
                self.send_error_response(-32602, "Invalid params: parts must be array")
                return
            
            # 错误 6: parts 为空
            if len(message['parts']) == 0:
                self.send_error_response(-32602, "Invalid params: parts cannot be empty")
                return
            
            # 错误 7: Part 类型无效
            for i, part in enumerate(message['parts']):
                if 'kind' not in part:
                    self.send_error_response(-32602, f"Invalid params: part[{i}] missing kind")
                    return
                if part['kind'] not in ['text', 'file', 'data']:
                    self.send_error_response(-32602, f"Invalid params: part[{i}] invalid kind: {part['kind']}")
                    return
            
            # 错误 8: 文件太大 (模拟)
            for i, part in enumerate(message['parts']):
                if part['kind'] == 'file':
                    file_data = part.get('file', {})
                    if 'bytes' in file_data and len(file_data['bytes']) > 1000000:
                        self.send_error_response(-32004, "File too large", {"maxSize": "1MB"})
                        return
            
            # 错误 9: base64 无效 (模拟)
            for i, part in enumerate(message['parts']):
                if part['kind'] == 'file':
                    file_data = part.get('file', {})
                    if 'bytes' in file_data:
                        try:
                            import base64
                            base64.b64decode(file_data['bytes'])
                        except:
                            self.send_error_response(-32005, "Invalid base64 encoding")
                            return
            
            # 正常响应
            self.send_json({
                "jsonrpc": "2.0",
                "id": self.request_id,
                "result": {
                    "kind": "message",
                    "messageId": str(uuid.uuid4()),
                    "parts": [{"kind": "text", "text": "OK"}],
                    "role": "agent"
                }
            })
        
        elif method == 'tasks/get':
            task_id = params.get('id')
            
            # 错误 10: Task 不存在
            if task_id != 'existing-task':
                self.send_error_response(-32001, f"Task not found: {task_id}")
                return
            
            self.send_json({
                "jsonrpc": "2.0",
                "id": self.request_id,
                "result": {
                    "id": task_id,
                    "status": {"state": "completed"},
                    "kind": "task"
                }
            })

if __name__ == '__main__':
    print("🚀 Error Demo Server running at http://127.0.0.1:9999/")
    print("="*60)
    print("测试错误场景:")
    print("  curl -X POST http://127.0.0.1:9999/ -d '{}'")
    print("  curl -X POST http://127.0.0.1:9999/ -d 'invalid'")
    print("  curl -X POST http://127.0.0.1:9999/ -d '{\"jsonrpc\":\"2.0\",\"method\":\"unknown\"}'")
    print("="*60)
    HTTPServer(('127.0.0.1', 9999), ErrorDemoHandler).serve_forever()
