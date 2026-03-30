#!/usr/bin/env python3
"""
A2A Protocol Client - 完整功能的 A2A 客户端

支持功能:
- Agent Card 获取
- message/send 同步消息
- message/stream 流式消息 (SSE)
- tasks/get 任务查询
- tasks/cancel 任务取消
- 多轮对话支持
- 文件传输支持
- 错误处理和重试
- 超时控制

使用示例:
    from client import A2AClient
    
    # 创建客户端
    client = A2AClient("http://127.0.0.1:8888")
    
    # 获取 Agent Card
    card = client.get_agent_card()
    print(f"Agent: {card['name']}")
    
    # 发送消息
    response = client.send_message("Hello!")
    print(f"Response: {response}")
"""

import json
import uuid
import base64
import time
from typing import Dict, List, Optional, Any, Generator, Union
from dataclasses import dataclass
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError


# =============================================================================
# 异常定义
# =============================================================================

class A2AError(Exception):
    """A2A 协议基础异常"""
    pass


class A2AConnectionError(A2AError):
    """连接错误"""
    pass


class A2ATimeoutError(A2AError):
    """超时错误"""
    pass


class A2ARPCError(A2AError):
    """JSON-RPC 错误"""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"RPC Error {code}: {message}")


class A2ANotFoundError(A2AError):
    """资源未找到"""
    pass


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class Message:
    """消息对象"""
    role: str
    parts: List[Dict]
    message_id: str
    context_id: Optional[str] = None
    task_id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        return cls(
            role=data.get("role", "user"),
            parts=data.get("parts", []),
            message_id=data.get("messageId", ""),
            context_id=data.get("contextId"),
            task_id=data.get("taskId")
        )


@dataclass
class Task:
    """任务对象"""
    id: str
    context_id: str
    status: str
    history: List[Message]
    artifacts: List[Dict]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        return cls(
            id=data.get("id", ""),
            context_id=data.get("contextId", ""),
            status=data.get("status", {}).get("state", "unknown"),
            history=[Message.from_dict(m) for m in data.get("history", [])],
            artifacts=data.get("artifacts", [])
        )


# =============================================================================
# 客户端实现
# =============================================================================

class A2AClient:
    """
    A2A Protocol 客户端
    
    示例:
        client = A2AClient("http://127.0.0.1:8888")
        
        # 获取 Agent Card
        card = client.get_agent_card()
        
        # 发送消息
        response = client.send_message("Hello!")
        
        # 流式消息
        for event in client.stream_message("Tell me a story"):
            print(event)
        
        # 多轮对话
        response1 = client.send_message("Hi", context_id=None)
        context_id = response1.get("contextId")
        response2 = client.send_message("How are you?", context_id=context_id)
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        初始化客户端
        
        参数:
            base_url: Agent 服务地址
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            headers: 自定义请求头
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = headers or {}
        
        # 会话管理
        self._session: Optional[requests.Session] = None
        self._request_id = 0
    
    @property
    def session(self) -> requests.Session:
        """获取或创建 requests 会话"""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                **self.headers
            })
        return self._session
    
    def _next_request_id(self) -> int:
        """生成下一个请求 ID"""
        self._request_id += 1
        return self._request_id
    
    def _make_request(
        self,
        method: str,
        params: Dict,
        retry_on_error: bool = True
    ) -> Dict:
        """
        发送 JSON-RPC 请求
        
        参数:
            method: JSON-RPC 方法名
            params: 方法参数
            retry_on_error: 是否在错误时重试
            
        返回:
            JSON-RPC 响应的 result 部分
            
        异常:
            A2AConnectionError: 连接失败
            A2ATimeoutError: 请求超时
            A2ARPCError: JSON-RPC 错误
        """
        request_id = self._next_request_id()
        
        request_body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.base_url,
                    json=request_body,
                    timeout=self.timeout
                )
                
                # 解析响应
                data = response.json()
                
                # 检查 JSON-RPC 错误
                if "error" in data:
                    error = data["error"]
                    raise A2ARPCError(
                        code=error.get("code", -1),
                        message=error.get("message", "Unknown error"),
                        data=error.get("data")
                    )
                
                return data.get("result", {})
                
            except Timeout as e:
                last_error = A2ATimeoutError(f"Request timeout: {e}")
                
            except ConnectionError as e:
                last_error = A2AConnectionError(f"Connection failed: {e}")
                
            except json.JSONDecodeError as e:
                last_error = A2AError(f"Invalid JSON response: {e}")
                
            except A2ARPCError:
                raise  # RPC 错误不重试
                
            except RequestException as e:
                last_error = A2AError(f"Request failed: {e}")
            
            # 重试前等待
            if retry_on_error and attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        
        raise last_error or A2AError("Unknown error")
    
    # -------------------------------------------------------------------------
    # Agent Card
    # -------------------------------------------------------------------------
    
    def get_agent_card(self) -> Dict:
        """
        获取 Agent Card
        
        Agent Card 包含:
        - Agent 名称和描述
        - 支持的能力
        - 技能列表
        - 安全方案
        
        返回:
            Agent Card 字典
            
        示例:
            card = client.get_agent_card()
            print(f"Agent: {card['name']}")
            print(f"Capabilities: {card['capabilities']}")
        """
        url = f"{self.base_url}/.well-known/agent.json"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
                
            except Timeout as e:
                if attempt == self.max_retries - 1:
                    raise A2ATimeoutError(f"Timeout getting agent card: {e}")
                    
            except ConnectionError as e:
                if attempt == self.max_retries - 1:
                    raise A2AConnectionError(f"Connection failed: {e}")
                    
            except RequestException as e:
                if attempt == self.max_retries - 1:
                    raise A2AError(f"Failed to get agent card: {e}")
            
            time.sleep(self.retry_delay * (attempt + 1))
        
        raise A2AError("Failed to get agent card")
    
    # -------------------------------------------------------------------------
    # 消息发送
    # -------------------------------------------------------------------------
    
    def send_message(
        self,
        text: Optional[str] = None,
        parts: Optional[List[Dict]] = None,
        context_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Dict:
        """
        发送消息 (message/send)
        
        参数:
            text: 文本消息内容（简化接口）
            parts: 消息部件列表（完整接口）
            context_id: 上下文 ID（用于多轮对话）
            task_id: 任务 ID
            message_id: 消息 ID（可选，自动生成）
            
        返回:
            响应消息字典
            
        示例:
            # 简单文本消息
            response = client.send_message("Hello!")
            
            # 多轮对话
            r1 = client.send_message("Hi")
            r2 = client.send_message("How are you?", context_id=r1.get("contextId"))
            
            # 发送文件
            with open("file.txt", "rb") as f:
                file_bytes = base64.b64encode(f.read()).decode()
            
            response = client.send_message(parts=[
                {"kind": "text", "text": "Please analyze this file"},
                {"kind": "file", "file": {
                    "name": "file.txt",
                    "mimeType": "text/plain",
                    "bytes": file_bytes
                }}
            ])
        """
        # 构建 parts
        if parts is None:
            if text is None:
                text = ""
            parts = [{"kind": "text", "text": text}]
        
        # 构建消息
        message = {
            "role": "user",
            "parts": parts,
            "messageId": message_id or str(uuid.uuid4())
        }
        
        if context_id:
            message["contextId"] = context_id
        if task_id:
            message["taskId"] = task_id
        
        return self._make_request("message/send", {"message": message})
    
    def send_file(
        self,
        file_path: str,
        text: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> Dict:
        """
        发送文件消息
        
        参数:
            file_path: 文件路径
            text: 附加文本消息
            context_id: 上下文 ID
            
        返回:
            响应消息字典
        """
        import mimetypes
        
        # 读取文件
        with open(file_path, "rb") as f:
            file_bytes = base64.b64encode(f.read()).decode()
        
        # 获取文件名和 MIME 类型
        import os
        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        
        # 构建 parts
        parts = []
        
        if text:
            parts.append({"kind": "text", "text": text})
        
        parts.append({
            "kind": "file",
            "file": {
                "name": filename,
                "mimeType": mime_type,
                "bytes": file_bytes
            }
        })
        
        return self.send_message(parts=parts, context_id=context_id)
    
    def send_data(
        self,
        data: Dict,
        text: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> Dict:
        """
        发送结构化数据消息
        
        参数:
            data: 结构化数据
            text: 附加文本消息
            context_id: 上下文 ID
            
        返回:
            响应消息字典
        """
        parts = []
        
        if text:
            parts.append({"kind": "text", "text": text})
        
        parts.append({"kind": "data", "data": data})
        
        return self.send_message(parts=parts, context_id=context_id)
    
    # -------------------------------------------------------------------------
    # 流式消息
    # -------------------------------------------------------------------------
    
    def stream_message(
        self,
        text: Optional[str] = None,
        parts: Optional[List[Dict]] = None,
        context_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Generator[Dict, None, None]:
        """
        发送流式消息 (message/stream)
        
        使用 SSE (Server-Sent Events) 接收流式响应。
        
        参数:
            text: 文本消息内容
            parts: 消息部件列表
            context_id: 上下文 ID
            task_id: 任务 ID
            message_id: 消息 ID
            
        生成:
            SSE 事件字典
            
        示例:
            for event in client.stream_message("Tell me a story"):
                if event.get("kind") == "artifact-update":
                    for part in event.get("artifact", {}).get("parts", []):
                        if "text" in part:
                            print(part["text"], end="")
                elif event.get("kind") == "status-update":
                    print(f"\nStatus: {event['status']['state']}")
        """
        # 构建 parts
        if parts is None:
            if text is None:
                text = ""
            parts = [{"kind": "text", "text": text}]
        
        # 构建消息
        message = {
            "role": "user",
            "parts": parts,
            "messageId": message_id or str(uuid.uuid4())
        }
        
        if context_id:
            message["contextId"] = context_id
        if task_id:
            message["taskId"] = task_id
        
        request_body = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "message/stream",
            "params": {"message": message}
        }
        
        # 发送请求并处理 SSE 流
        response = self.session.post(
            self.base_url,
            json=request_body,
            timeout=self.timeout,
            stream=True
        )
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            # 跳过注释行
            if line.startswith(':'):
                continue
            
            # 解析 SSE 数据
            if line.startswith('data: '):
                data_str = line[6:]
                try:
                    event = json.loads(data_str)
                    yield event
                except json.JSONDecodeError:
                    continue
    
    def stream_text(
        self,
        text: str,
        context_id: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        流式接收文本响应（简化接口）
        
        参数:
            text: 文本消息
            context_id: 上下文 ID
            
        生成:
            文本片段
            
        示例:
            for chunk in client.stream_text("Hello"):
                print(chunk, end="", flush=True)
        """
        for event in self.stream_message(text, context_id=context_id):
            if event.get("kind") == "artifact-update":
                artifact = event.get("artifact", {})
                if artifact.get("lastChunk", False):
                    # 只在最后一块时返回完整文本
                    for part in artifact.get("parts", []):
                        if "text" in part:
                            yield part["text"]
    
    # -------------------------------------------------------------------------
    # 任务管理
    # -------------------------------------------------------------------------
    
    def get_task(self, task_id: str) -> Task:
        """
        获取任务状态 (tasks/get)
        
        参数:
            task_id: 任务 ID
            
        返回:
            Task 对象
            
        示例:
            task = client.get_task("task-123")
            print(f"Status: {task.status}")
            print(f"Artifacts: {len(task.artifacts)}")
        """
        result = self._make_request("tasks/get", {"id": task_id})
        return Task.from_dict(result)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务 (tasks/cancel)
        
        参数:
            task_id: 任务 ID
            
        返回:
            是否成功取消
            
        示例:
            success = client.cancel_task("task-123")
            print(f"Cancelled: {success}")
        """
        result = self._make_request("tasks/cancel", {"id": task_id})
        return result.get("success", False)
    
    # -------------------------------------------------------------------------
    # 便捷方法
    # -------------------------------------------------------------------------
    
    def chat(self, messages: List[str]) -> List[Dict]:
        """
        多轮对话（便捷接口）
        
        参数:
            messages: 消息列表
            
        返回:
            响应列表
            
        示例:
            responses = client.chat([
                "Hello!",
                "How are you?",
                "Goodbye!"
            ])
            for i, r in enumerate(responses):
                print(f"Turn {i+1}: {r['parts'][0]['text']}")
        """
        results = []
        context_id = None
        
        for msg in messages:
            response = self.send_message(msg, context_id=context_id)
            results.append(response)
            context_id = response.get("contextId")
        
        return results
    
    def close(self):
        """关闭客户端会话"""
        if self._session:
            self._session.close()
            self._session = None
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='A2A Protocol Client')
    parser.add_argument('url', help='Agent URL (e.g., http://127.0.0.1:8888)')
    parser.add_argument('--card', action='store_true', help='Get agent card')
    parser.add_argument('--send', type=str, help='Send a message')
    parser.add_argument('--stream', type=str, help='Send a streaming message')
    parser.add_argument('--chat', nargs='+', help='Multi-turn conversation')
    parser.add_argument('--file', type=str, help='Send a file')
    parser.add_argument('--timeout', type=float, default=30.0, help='Request timeout')
    
    args = parser.parse_args()
    
    # 创建客户端
    with A2AClient(args.url, timeout=args.timeout) as client:
        if args.card:
            # 获取 Agent Card
            card = client.get_agent_card()
            print(json.dumps(card, indent=2, ensure_ascii=False))
        
        elif args.send:
            # 发送消息
            response = client.send_message(args.send)
            print(json.dumps(response, indent=2, ensure_ascii=False))
        
        elif args.stream:
            # 流式消息
            for event in client.stream_message(args.stream):
                if event.get("kind") == "artifact-update":
                    artifact = event.get("artifact", {})
                    for part in artifact.get("parts", []):
                        if "text" in part:
                            print(part["text"])
                elif event.get("kind") == "status-update":
                    print(f"\n[Status: {event['status']['state']}]")
        
        elif args.chat:
            # 多轮对话
            responses = client.chat(args.chat)
            for i, r in enumerate(responses):
                print(f"\n--- Turn {i+1} ---")
                print(json.dumps(r, indent=2, ensure_ascii=False))
        
        elif args.file:
            # 发送文件
            response = client.send_file(args.file, text="Please analyze this file")
            print(json.dumps(response, indent=2, ensure_ascii=False))
        
        else:
            # 默认：获取 Agent Card
            card = client.get_agent_card()
            print(json.dumps(card, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
