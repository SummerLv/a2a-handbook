#!/usr/bin/env python3
"""
完整的 A2A 服务端实现
支持：多轮对话、文件传输、SSE 流式响应、任务管理

启动: python3 full_server.py
测试: curl http://127.0.0.1:8888/.well-known/agent.json
"""

import json
import uuid
import time
import base64
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ==================== 数据模型 ====================

@dataclass
class Task:
    """任务对象"""
    id: str
    context_id: str
    status: dict
    history: List[dict] = field(default_factory=list)
    artifacts: List[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

# ==================== 任务存储 ====================

tasks: Dict[str, Task] = {}
contexts: Dict[str, dict] = {}

# ==================== Agent 配置 ====================

AGENT_CARD = {
    "name": "Full-Featured A2A Agent",
    "description": "支持多轮对话、文件传输、流式响应的完整 A2A Agent",
    "version": "2.0.0",
    "capabilities": {
        "streaming": True,
        "push_notifications": True,
        "extended_agent_card": True
    },
    "defaultInputModes": ["text", "application/json"],
    "defaultOutputModes": ["text", "application/json"],
    "skills": [
        {
            "id": "chat",
            "name": "多轮对话",
            "description": "支持上下文的多轮对话",
            "tags": ["chat", "conversation"],
            "examples": ["你好", "继续聊聊"]
        },
        {
            "id": "file_process",
            "name": "文件处理",
            "description": "接收并处理文件",
            "tags": ["file", "upload"],
            "examples": ["分析这个文件", "处理这个图片"]
        },
        {
            "id": "long_task",
            "name": "长任务",
            "description": "模拟耗时操作，支持进度更新",
            "tags": ["task", "async"],
            "examples": ["生成报告", "批量处理"]
        }
    ],
    "url": "http://127.0.0.1:8888/",
    "securitySchemes": {
        "bearer": {
            "type": "http",
            "scheme": "bearer",
            "description": "Bearer Token 认证"
        }
    }
}

# ==================== 业务逻辑 ====================

def process_text(text: str, context: Optional[dict] = None) -> str:
    """处理文本消息"""
    # 这里可以接入 LLM 或其他处理逻辑
    turn = context.get('turn_count', 0) if context else 0
    
    # 模拟不同场景
    if '预订' in text or 'book' in text.lower():
        return "好的，请告诉我更多详情？比如日期、地点？"
    
    if turn > 0:
        return f"[第{turn}轮] 收到: {text}"
    
    return f"收到消息: {text}"

def process_file(file_info: dict) -> str:
    """处理文件"""
    name = file_info.get('name', 'unknown')
    mime_type = file_info.get('mimeType', 'unknown')
    size = len(base64.b64decode(file_info.get('bytes', ''))) if 'bytes' in file_info else 0
    
    return f"收到文件: {name}, 类型: {mime_type}, 大小: {size} bytes"

def generate_sse_events(task_id: str, text: str) -> str:
    """生成 SSE 流式响应"""
    words = f"处理中... {text}".split()
    events = []
    
    for i, word in enumerate(words):
        event = {
            "jsonrpc": "2.0",
            "id": None,
            "result": {
                "taskId": task_id,
                "artifact": {
                    "artifactId": str(uuid.uuid4()),
                    "parts": [{"kind": "text", "text": word + " "}]
                },
                "append": i > 0,
                "lastChunk": i == len(words) - 1,
                "kind": "artifact-update"
            }
        }
        events.append(f"data: {json.dumps(event)}\n\n")
    
    # 最终状态
    final = {
        "jsonrpc": "2.0",
        "id": None,
        "result": {
            "taskId": task_id,
            "status": {"state": "completed", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
            "final": True,
            "kind": "status-update"
        }
    }
    events.append(f"data: {json.dumps(final)}\n\n")
    
    return "".join(events)

# ==================== HTTP Handler ====================

class A2AHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    
    def log_message(self, format, *args):
        print(f"[{self.command}] {args[0]}")

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_sse(self, events: str):
        body = events.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        print(f"\n{'='*60}")
        print(f"📥 GET {self.path}")
        print(f"{'='*60}")
        
        if self.path == '/.well-known/agent.json':
            print("📋 返回 Agent Card")
            self.send_json(AGENT_CARD)
        elif self.path.startswith('/tasks/'):
            task_id = self.path.split('/')[-1]
            if task_id in tasks:
                task = tasks[task_id]
                self.send_json({
                    "jsonrpc": "2.0",
                    "id": None,
                    "result": {
                        "id": task.id,
                        "contextId": task.context_id,
                        "status": task.status,
                        "history": task.history,
                        "artifacts": task.artifacts,
                        "kind": "task"
                    }
                })
            else:
                self.send_json({"error": "Task not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        print(f"\n{'='*60}")
        print(f"📤 POST {self.path}")
        print(f"{'='*60}")
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        
        print(f"📨 Request:\n{json.dumps(request, indent=2, ensure_ascii=False)}")
        
        if self.path == '/':
            self.handle_jsonrpc(request)
        else:
            self.send_json({"error": "Not found"}, 404)

    def handle_jsonrpc(self, request: dict):
        method = request.get('method')
        params = request.get('params', {})
        req_id = request.get('id')
        
        handlers = {
            'message/send': self.handle_message_send,
            'message/stream': self.handle_message_stream,
            'tasks/get': self.handle_tasks_get,
            'tasks/cancel': self.handle_tasks_cancel,
        }
        
        handler = handlers.get(method)
        if handler:
            handler(req_id, params)
        else:
            self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

    def handle_message_send(self, req_id, params):
        """处理普通消息"""
        message = params.get('message', {})
        parts = message.get('parts', [])
        context_id = message.get('contextId')
        task_id = message.get('taskId')
        
        # 提取内容
        response_text = ""
        for part in parts:
            if part.get('kind') == 'text':
                text = part.get('text', '')
                context = contexts.get(context_id) if context_id else None
                response_text = process_text(text, context)
            elif part.get('kind') == 'file':
                response_text = process_file(part.get('file', {}))
        
        # 管理上下文
        if context_id and context_id in contexts:
            contexts[context_id]['turn_count'] += 1
        else:
            context_id = str(uuid.uuid4())
            contexts[context_id] = {'turn_count': 1, 'created_at': time.time()}
        
        # 判断是否需要更多输入
        if '预订' in str(parts):
            task_id = task_id or str(uuid.uuid4())
            tasks[task_id] = Task(
                id=task_id,
                context_id=context_id,
                status={"state": "input-required"},
                history=[message]
            )
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {
                        "state": "input-required",
                        "message": {
                            "role": "agent",
                            "parts": [{"kind": "text", "text": response_text}],
                            "messageId": str(uuid.uuid4())
                        }
                    },
                    "history": [message],
                    "kind": "task"
                }
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "kind": "message",
                    "messageId": str(uuid.uuid4()),
                    "contextId": context_id,
                    "parts": [{"kind": "text", "text": response_text}],
                    "role": "agent"
                }
            }
        
        print(f"📨 Response:\n{json.dumps(response, indent=2, ensure_ascii=False)}")
        self.send_json(response)

    def handle_message_stream(self, req_id, params):
        """处理流式消息"""
        message = params.get('message', {})
        text = next((p['text'] for p in message.get('parts', []) if p['kind'] == 'text'), '')
        
        task_id = str(uuid.uuid4())
        tasks[task_id] = Task(
            id=task_id,
            context_id=str(uuid.uuid4()),
            status={"state": "working"}
        )
        
        print(f"🌊 SSE 流式响应, taskId: {task_id}")
        events = generate_sse_events(task_id, text)
        self.send_sse(events)
        
        tasks[task_id].status["state"] = "completed"

    def handle_tasks_get(self, req_id, params):
        """查询任务状态"""
        task_id = params.get('id')
        if task_id in tasks:
            task = tasks[task_id]
            self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task.id,
                    "contextId": task.context_id,
                    "status": task.status,
                    "kind": "task"
                }
            })
        else:
            self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32001, "message": "Task not found"}
            })

    def handle_tasks_cancel(self, req_id, params):
        """取消任务"""
        task_id = params.get('id')
        if task_id in tasks:
            tasks[task_id].status["state"] = "cancelled"
            self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "status": {"state": "cancelled"},
                    "kind": "task"
                }
            })
        else:
            self.send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32001, "message": "Task not found"}
            })

# ==================== 启动服务 ====================

if __name__ == '__main__':
    HOST, PORT = '127.0.0.1', 8888
    server = HTTPServer((HOST, PORT), A2AHandler)
    
    print(f"🚀 Full A2A Server running at http://{HOST}:{PORT}/")
    print(f"📋 Agent Card: http://{HOST}:{PORT}/.well-known/agent.json")
    print("="*60)
    print("支持功能:")
    print("  ✅ message/send    - 普通消息 & 多轮对话")
    print("  ✅ message/stream  - SSE 流式响应")
    print("  ✅ tasks/get       - 查询任务状态")
    print("  ✅ tasks/cancel    - 取消任务")
    print("  ✅ 文件上传处理")
    print("="*60)
    
    server.serve_forever()
