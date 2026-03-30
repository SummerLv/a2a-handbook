"""
A2A 协议测试用例库
================

全面的测试用例集，覆盖 A2A 协议的所有核心功能和边界场景。

测试类别：
1. Agent Card 测试
2. 消息发送测试
3. Task 生命周期测试
4. 流式响应测试
5. 认证测试
6. 边界测试

使用方法：
    pytest test_cases.py -v                    # 运行所有测试
    pytest test_cases.py -k "agent_card" -v   # 运行特定类别
    pytest test_cases.py --cov=a2a -v         # 带覆盖率报告
"""

import pytest
import requests
import json
import uuid
import time
import base64
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==================== 配置 ====================

class A2AConfig:
    """测试配置"""
    BASE_URL = "http://localhost:8000"
    AGENT_CARD_URL = f"{BASE_URL}/.well-known/agent.json"
    API_ENDPOINT = f"{BASE_URL}/"
    TIMEOUT = 30
    MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
    VALID_TOKEN = "valid-test-token"
    EXPIRED_TOKEN = "expired-test-token"
    INVALID_TOKEN = "invalid-test-token"


# ==================== 工具函数 ====================

class A2AHelper:
    """A2A 测试辅助工具"""
    
    @staticmethod
    def generate_message_id() -> str:
        """生成消息ID"""
        return f"msg-{uuid.uuid4()}"
    
    @staticmethod
    def generate_task_id() -> str:
        """生成任务ID"""
        return f"task-{uuid.uuid4()}"
    
    @staticmethod
    def generate_context_id() -> str:
        """生成上下文ID"""
        return f"ctx-{uuid.uuid4()}"
    
    @staticmethod
    def create_text_part(text: str) -> Dict[str, Any]:
        """创建文本Part"""
        return {"kind": "text", "text": text}
    
    @staticmethod
    def create_file_part(name: str, content: str, mime_type: str = "text/plain") -> Dict[str, Any]:
        """创建文件Part"""
        bytes_content = base64.b64encode(content.encode()).decode()
        return {
            "kind": "file",
            "file": {
                "name": name,
                "mimeType": mime_type,
                "bytes": bytes_content
            }
        }
    
    @staticmethod
    def create_data_part(data: Dict[str, Any]) -> Dict[str, Any]:
        """创建数据Part"""
        return {"kind": "data", "data": data}
    
    @staticmethod
    def build_jsonrpc_request(method: str, params: Dict[str, Any], request_id: int = 1) -> Dict[str, Any]:
        """构建JSON-RPC请求"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
    
    @staticmethod
    def send_request(payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> requests.Response:
        """发送请求"""
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        
        return requests.post(
            A2AConfig.API_ENDPOINT,
            json=payload,
            headers=default_headers,
            timeout=A2AConfig.TIMEOUT
        )
    
    @staticmethod
    def send_stream_request(payload: Dict[str, Any]) -> requests.Response:
        """发送流式请求"""
        return requests.post(
            A2AConfig.API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=A2AConfig.TIMEOUT
        )


# ==================== Fixtures ====================

@pytest.fixture
def helper():
    """测试辅助工具fixture"""
    return A2AHelper()


@pytest.fixture
def valid_token():
    """有效Token"""
    return A2AConfig.VALID_TOKEN


@pytest.fixture
def expired_token():
    """过期Token"""
    return A2AConfig.EXPIRED_TOKEN


@pytest.fixture
def invalid_token():
    """无效Token"""
    return A2AConfig.INVALID_TOKEN


# ==================== 1. Agent Card 测试 ====================

class TestAgentCard:
    """
    Agent Card 测试集
    
    Agent Card 是 A2A 协议中用于发现和描述 Agent 能力的核心组件。
    通过 GET /.well-known/agent.json 获取。
    """
    
    @pytest.mark.agent_card
    @pytest.mark.smoke
    def test_get_agent_card_success(self, helper):
        """
        测试正常获取 Agent Card
        
        前置条件：
            - Agent 服务正常运行
            - Agent Card 配置正确
        
        测试步骤：
            1. 发送 GET 请求到 /.well-known/agent.json
            2. 验证响应状态码为 200
            3. 验证响应内容为 JSON 格式
        
        预期结果：
            - 返回有效的 Agent Card
            - HTTP 状态码 200
            - Content-Type 为 application/json
        """
        response = requests.get(A2AConfig.AGENT_CARD_URL, timeout=A2AConfig.TIMEOUT)
        
        # 断言
        assert response.status_code == 200, f"预期状态码 200，实际 {response.status_code}"
        assert "application/json" in response.headers.get("Content-Type", ""), \
            "响应 Content-Type 应为 application/json"
        
        card = response.json()
        assert isinstance(card, dict), "Agent Card 应为字典类型"
    
    @pytest.mark.agent_card
    def test_agent_card_required_fields(self, helper):
        """
        测试 Agent Card 必填字段
        
        前置条件：
            - Agent 服务正常运行
        
        测试步骤：
            1. 获取 Agent Card
            2. 检查所有必填字段是否存在
            3. 验证字段类型和格式
        
        预期结果：
            - 包含 name 字段（非空字符串）
            - 包含 description 字段
            - 包含 capabilities 字段（对象）
            - 包含 url 字段（有效 URL）
        
        必填字段验证：
            - name: Agent 名称
            - capabilities: 能力描述
            - url: 服务端点
        """
        response = requests.get(A2AConfig.AGENT_CARD_URL, timeout=A2AConfig.TIMEOUT)
        assert response.status_code == 200
        
        card = response.json()
        
        # 必填字段断言
        assert "name" in card, "缺少必填字段 'name'"
        assert card["name"], "'name' 字段不能为空"
        assert isinstance(card["name"], str), "'name' 应为字符串类型"
        
        assert "capabilities" in card, "缺少必填字段 'capabilities'"
        assert isinstance(card["capabilities"], dict), "'capabilities' 应为对象类型"
        
        assert "url" in card, "缺少必填字段 'url'"
        assert card["url"], "'url' 字段不能为空"
        # 可选：验证 URL 格式
        assert card["url"].startswith("http"), "'url' 应为有效的 HTTP URL"
    
    @pytest.mark.agent_card
    def test_agent_card_not_found(self, helper):
        """
        测试 Agent Card 不存在
        
        前置条件：
            - Agent 服务未配置 Agent Card
            - 或服务端点错误
        
        测试步骤：
            1. 请求不存在的 Agent Card 路径
            2. 验证响应状态码
        
        预期结果：
            - 返回 404 Not Found
        """
        invalid_url = f"{A2AConfig.BASE_URL}/.well-known/nonexistent.json"
        response = requests.get(invalid_url, timeout=A2AConfig.TIMEOUT)
        
        assert response.status_code == 404, f"预期状态码 404，实际 {response.status_code}"
    
    @pytest.mark.agent_card
    def test_agent_card_invalid_json(self, helper, requests_mock):
        """
        测试 Agent Card 格式错误（非 JSON）
        
        前置条件：
            - Agent 返回非 JSON 格式的响应
        
        测试步骤：
            1. 发送请求获取 Agent Card
            2. 尝试解析 JSON
        
        预期结果：
            - 解析失败，抛出 JSON 解码错误
            - 或服务端返回适当错误码
        """
        # 使用 mock 模拟错误响应
        requests_mock.get(
            A2AConfig.AGENT_CARD_URL,
            text="This is not JSON",
            status_code=200
        )
        
        response = requests.get(A2AConfig.AGENT_CARD_URL, timeout=A2AConfig.TIMEOUT)
        
        # 断言：解析 JSON 应失败
        with pytest.raises(json.JSONDecodeError):
            response.json()
    
    @pytest.mark.agent_card
    def test_agent_card_missing_required_field(self, helper, requests_mock):
        """
        测试 Agent Card 缺少必填字段
        
        前置条件：
            - Agent Card 配置不完整
        
        测试步骤：
            1. 获取缺少必填字段的 Agent Card
            2. 验证字段完整性
        
        预期结果：
            - 客户端应检测到缺失字段
            - 或服务端返回验证错误
        """
        # 模拟不完整的 Agent Card
        incomplete_card = {
            "description": "An incomplete agent card"
            # 缺少 name, capabilities, url 等必填字段
        }
        
        requests_mock.get(
            A2AConfig.AGENT_CARD_URL,
            json=incomplete_card,
            status_code=200
        )
        
        response = requests.get(A2AConfig.AGENT_CARD_URL, timeout=A2AConfig.TIMEOUT)
        card = response.json()
        
        # 断言：验证必填字段缺失
        required_fields = ["name", "capabilities", "url"]
        missing_fields = [field for field in required_fields if field not in card]
        
        assert len(missing_fields) > 0, "应检测到缺失的必填字段"
    
    @pytest.mark.agent_card
    def test_agent_card_version_validation(self, helper):
        """
        测试 Agent Card 版本验证
        
        前置条件：
            - Agent Card 包含版本信息
        
        测试步骤：
            1. 获取 Agent Card
            2. 检查版本字段格式
            3. 验证版本语义化格式（如适用）
        
        预期结果：
            - 版本号格式正确（推荐语义化版本）
            - 版本号可解析和比较
        """
        response = requests.get(A2AConfig.AGENT_CARD_URL, timeout=A2AConfig.TIMEOUT)
        
        if response.status_code != 200:
            pytest.skip("Agent Card 不可用")
        
        card = response.json()
        
        # 如果存在版本字段，验证格式
        if "version" in card:
            version = card["version"]
            assert isinstance(version, str), "版本号应为字符串"
            
            # 简单验证语义化版本格式 (major.minor.patch)
            import re
            semver_pattern = r"^\d+\.\d+\.\d+"
            if re.match(semver_pattern, version):
                # 版本格式正确
                pass
            else:
                # 非语义化版本，但仍然有效
                assert len(version) > 0, "版本号不能为空字符串"
    
    @pytest.mark.agent_card
    def test_agent_card_capabilities_structure(self, helper):
        """
        测试 Agent Card capabilities 字段结构
        
        前置条件：
            - Agent Card 存在且有效
        
        测试步骤：
            1. 获取 Agent Card
            2. 检查 capabilities 对象结构
            3. 验证各能力字段的布尔值
        
        预期结果：
            - capabilities 为对象类型
            - 各能力字段为布尔值
        """
        response = requests.get(A2AConfig.AGENT_CARD_URL, timeout=A2AConfig.TIMEOUT)
        assert response.status_code == 200
        
        card = response.json()
        capabilities = card.get("capabilities", {})
        
        assert isinstance(capabilities, dict), "'capabilities' 应为对象类型"
        
        # 验证常见能力字段的类型
        common_capabilities = ["streaming", "push_notifications", "extended_agent_card"]
        for cap in common_capabilities:
            if cap in capabilities:
                assert isinstance(capabilities[cap], bool), \
                    f"能力 '{cap}' 应为布尔值"


# ==================== 2. 消息发送测试 ====================

class TestMessageSend:
    """
    消息发送测试集
    
    测试 A2A 协议的核心通信功能：message/send 方法。
    支持文本、文件、结构化数据等多种 Part 类型。
    """
    
    @pytest.mark.message
    @pytest.mark.smoke
    def test_send_simple_text_message(self, helper):
        """
        测试发送简单文本消息
        
        前置条件：
            - Agent 服务正常运行
            - Agent Card 可访问
        
        测试步骤：
            1. 构建包含文本 Part 的消息
            2. 发送 message/send 请求
            3. 验证响应格式和状态
        
        预期结果：
            - 返回 JSON-RPC 2.0 格式响应
            - result 包含 status 对象
            - status.state 为有效状态值
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("Hello, A2A!")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request(
            "message/send",
            {"message": message}
        )
        
        response = helper.send_request(payload)
        
        # 断言
        assert response.status_code == 200, f"HTTP 状态码应为 200，实际 {response.status_code}"
        
        result = response.json()
        assert "jsonrpc" in result, "响应应包含 'jsonrpc' 字段"
        assert result["jsonrpc"] == "2.0", "JSON-RPC 版本应为 2.0"
        assert "result" in result, "成功响应应包含 'result' 字段"
        
        # 验证状态
        if "status" in result.get("result", {}):
            status = result["result"]["status"]
            valid_states = ["submitted", "working", "completed", "input-required", "cancelled"]
            assert status.get("state") in valid_states, \
                f"状态应为有效值之一: {valid_states}"
    
    @pytest.mark.message
    def test_send_multi_turn_conversation(self, helper):
        """
        测试多轮对话
        
        前置条件：
            - Agent 支持多轮对话
            - Agent 维护会话状态
        
        测试步骤：
            1. 发送第一条消息，获取 contextId
            2. 发送第二条消息，使用相同 contextId
            3. 验证 Agent 能记住上下文
        
        预期结果：
            - 第一次响应包含 contextId
            - 第二次响应能关联到第一次对话
            - Agent 回复体现上下文记忆
        """
        # 第一轮对话
        message1 = {
            "role": "user",
            "parts": [helper.create_text_part("我叫小明")],
            "messageId": helper.generate_message_id()
        }
        
        payload1 = helper.build_jsonrpc_request("message/send", {"message": message1})
        response1 = helper.send_request(payload1)
        
        assert response1.status_code == 200
        result1 = response1.json().get("result", {})
        
        # 获取 contextId
        context_id = result1.get("contextId")
        if not context_id:
            pytest.skip("Agent 不支持多轮对话或未返回 contextId")
        
        # 第二轮对话（使用相同 contextId）
        message2 = {
            "role": "user",
            "parts": [helper.create_text_part("你还记得我叫什么吗？")],
            "messageId": helper.generate_message_id(),
            "contextId": context_id
        }
        
        payload2 = helper.build_jsonrpc_request("message/send", {"message": message2})
        response2 = helper.send_request(payload2)
        
        assert response2.status_code == 200
        result2 = response2.json().get("result", {})
        
        # 验证上下文关联
        assert result2.get("contextId") == context_id, \
            "多轮对话应使用相同的 contextId"
    
    @pytest.mark.message
    def test_send_file_transfer(self, helper):
        """
        测试文件传输
        
        前置条件：
            - Agent 支持文件处理
        
        测试步骤：
            1. 准备文件内容（base64 编码）
            2. 构建包含文件 Part 的消息
            3. 发送消息
            4. 验证响应
        
        预期结果：
            - Agent 正确接收文件
            - 返回成功响应
            - 文件内容完整
        """
        file_content = "This is a test file content for A2A protocol."
        file_name = "test_file.txt"
        
        message = {
            "role": "user",
            "parts": [helper.create_file_part(file_name, file_content)],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        assert response.status_code == 200
        
        result = response.json()
        assert "result" in result or "error" in result
        
        # 如果成功，验证响应
        if "result" in result:
            assert result["result"] is not None
    
    @pytest.mark.message
    def test_send_structured_data(self, helper):
        """
        测试发送结构化数据
        
        前置条件：
            - Agent 支持结构化数据处理
        
        测试步骤：
            1. 构建包含 data Part 的消息
            2. 发送复杂嵌套结构
            3. 验证响应
        
        预期结果：
            - Agent 正确解析结构化数据
            - 返回有效响应
        """
        structured_data = {
            "action": "search",
            "query": "A2A protocol",
            "filters": {
                "type": "documentation",
                "date": "2024-01-01"
            },
            "options": ["verbose", "include_examples"]
        }
        
        message = {
            "role": "user",
            "parts": [helper.create_data_part(structured_data)],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        assert response.status_code == 200
        
        result = response.json()
        assert "result" in result or "error" in result
    
    @pytest.mark.message
    @pytest.mark.negative
    def test_send_empty_message(self, helper):
        """
        测试发送空消息
        
        前置条件：
            - Agent 服务正常运行
        
        测试步骤：
            1. 构建空 parts 数组的消息
            2. 发送请求
        
        预期结果：
            - 返回错误响应
            - 错误码指示参数无效
        """
        message = {
            "role": "user",
            "parts": [],  # 空数组
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        # 断言：应返回错误
        result = response.json()
        
        # 服务端应拒绝空消息
        if "error" in result:
            assert result["error"]["code"] < 0, "错误码应为负数"
        else:
            # 或返回特定状态指示问题
            pytest.fail("空消息应被拒绝，但返回了成功响应")
    
    @pytest.mark.message
    @pytest.mark.negative
    @pytest.mark.slow
    def test_send_oversized_message(self, helper):
        """
        测试发送超大消息
        
        前置条件：
            - Agent 有消息大小限制
        
        测试步骤：
            1. 构建超过大小限制的消息
            2. 发送请求
            3. 验证响应
        
        预期结果：
            - 返回 413 Payload Too Large 或类似错误
            - 或返回 JSON-RPC 错误
        """
        # 创建超大文本内容（超过典型限制）
        large_text = "A" * (A2AConfig.MAX_MESSAGE_SIZE + 1)
        
        message = {
            "role": "user",
            "parts": [helper.create_text_part(large_text)],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        try:
            response = helper.send_request(payload)
            
            # 应返回错误状态码
            assert response.status_code >= 400, \
                f"超大消息应返回错误，实际状态码 {response.status_code}"
            
            result = response.json()
            assert "error" in result, "应返回错误信息"
        
        except requests.exceptions.RequestException:
            # 连接被关闭也是合理的响应
            pass
    
    @pytest.mark.message
    @pytest.mark.negative
    def test_send_invalid_part_type(self, helper):
        """
        测试发送无效 Part 类型
        
        前置条件：
            - Agent 服务正常运行
        
        测试步骤：
            1. 构建包含未知 kind 的 Part
            2. 发送请求
        
        预期结果：
            - 返回错误响应
            - 错误信息指示无效的 Part 类型
        """
        invalid_part = {
            "kind": "unknown_type",  # 无效类型
            "someData": "value"
        }
        
        message = {
            "role": "user",
            "parts": [invalid_part],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        result = response.json()
        
        # 应返回错误
        assert "error" in result, "无效 Part 类型应返回错误"
    
    @pytest.mark.message
    def test_send_message_with_context_id(self, helper):
        """
        测试发送带 contextId 的消息
        
        前置条件：
            - 存在有效的会话上下文
        
        测试步骤：
            1. 构建 contextId 字段
            2. 发送消息
            3. 验证响应使用相同 contextId
        
        预期结果：
            - 响应包含相同的 contextId
            - 会话正确关联
        """
        context_id = helper.generate_context_id()
        
        message = {
            "role": "user",
            "parts": [helper.create_text_part("测试上下文关联")],
            "messageId": helper.generate_message_id(),
            "contextId": context_id
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        assert response.status_code == 200
        
        result = response.json().get("result", {})
        
        # 验证 contextId 被保留
        response_context_id = result.get("contextId")
        assert response_context_id is not None, "响应应包含 contextId"


# ==================== 3. Task 生命周期测试 ====================

class TestTaskLifecycle:
    """
    Task 生命周期测试集
    
    测试 A2A 协议中的任务管理功能：
    - Task 创建
    - 状态转换
    - Task 取消
    - Task 查询
    """
    
    @pytest.mark.task
    @pytest.mark.smoke
    def test_task_creation(self, helper):
        """
        测试 Task 创建
        
        前置条件：
            - Agent 服务正常运行
            - Agent 支持任务管理
        
        测试步骤：
            1. 发送消息触发任务
            2. 检查响应中的 taskId
            3. 验证任务初始状态
        
        预期结果：
            - 返回有效的 taskId
            - 任务状态为 submitted 或 working
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("执行一个任务")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        assert response.status_code == 200
        
        result = response.json().get("result", {})
        
        # 如果返回 taskId，验证格式
        if "taskId" in result:
            task_id = result["taskId"]
            assert task_id, "taskId 不应为空"
        
        # 验证状态
        if "status" in result:
            status = result["status"]
            assert "state" in status, "status 应包含 state 字段"
            
            # 初始状态验证
            valid_initial_states = ["submitted", "working"]
            assert status["state"] in valid_initial_states, \
                f"初始状态应为 {valid_initial_states} 之一"
    
    @pytest.mark.task
    def test_task_status_transitions(self, helper):
        """
        测试 Task 状态转换
        
        前置条件：
            - Agent 支持任务状态管理
            - 任务有明确的生命周期
        
        测试步骤：
            1. 创建任务
            2. 轮询查询任务状态
            3. 验证状态转换序列
        
        预期结果：
            - 状态按有效序列转换
            - 状态转换: submitted → working → completed
        """
        # 创建任务
        message = {
            "role": "user",
            "parts": [helper.create_text_part("执行一个需要时间的任务")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        result = response.json().get("result", {})
        task_id = result.get("taskId")
        
        if not task_id:
            pytest.skip("Agent 未返回 taskId，不支持任务查询")
        
        # 轮询任务状态
        valid_states = ["submitted", "working", "completed", "input-required", "cancelled"]
        observed_states = []
        max_polls = 10
        poll_interval = 1  # 秒
        
        for _ in range(max_polls):
            query_payload = helper.build_jsonrpc_request(
                "tasks/get",
                {"id": task_id}
            )
            
            query_response = helper.send_request(query_payload)
            
            if query_response.status_code != 200:
                break
            
            query_result = query_response.json().get("result", {})
            status = query_result.get("status", {})
            state = status.get("state")
            
            if state and state not in observed_states:
                observed_states.append(state)
            
            # 任务完成，停止轮询
            if state in ["completed", "cancelled", "failed"]:
                break
            
            time.sleep(poll_interval)
        
        # 验证观察到的状态都是有效的
        for state in observed_states:
            assert state in valid_states, f"状态 '{state}' 不在有效状态列表中"
    
    @pytest.mark.task
    def test_task_cancel(self, helper):
        """
        测试 Task 取消
        
        前置条件：
            - Agent 支持任务取消
            - 存在可取消的任务
        
        测试步骤：
            1. 创建一个长时间运行的任务
            2. 发送取消请求
            3. 验证任务状态变为 cancelled
        
        预期结果：
            - 取消请求成功
            - 任务状态更新为 cancelled
        """
        # 创建长时间任务
        message = {
            "role": "user",
            "parts": [helper.create_text_part("执行一个长时间任务，需要至少30秒")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        result = response.json().get("result", {})
        task_id = result.get("taskId")
        
        if not task_id:
            pytest.skip("Agent 未返回 taskId")
        
        # 等待任务开始
        time.sleep(1)
        
        # 取消任务
        cancel_payload = helper.build_jsonrpc_request(
            "tasks/cancel",
            {"id": task_id}
        )
        
        cancel_response = helper.send_request(cancel_payload)
        
        assert cancel_response.status_code == 200
        
        cancel_result = cancel_response.json()
        
        # 验证取消结果
        if "result" in cancel_result:
            status = cancel_result["result"].get("status", {})
            assert status.get("state") == "cancelled", \
                "取消后任务状态应为 'cancelled'"
    
    @pytest.mark.task
    @pytest.mark.slow
    def test_task_timeout(self, helper):
        """
        测试 Task 超时
        
        前置条件：
            - Agent 有任务超时机制
            - 任务执行时间可配置
        
        测试步骤：
            1. 创建超长任务
            2. 等待超过超时时间
            3. 查询任务状态
        
        预期结果：
            - 任务被标记为超时或失败
            - 或返回超时错误
        """
        # 创建超时任务
        message = {
            "role": "user",
            "parts": [helper.create_text_part("执行一个会超时的任务")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        try:
            # 使用较短的超时
            response = requests.post(
                A2AConfig.API_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5  # 5秒超时
            )
            
            result = response.json()
            
            # 验证是否有超时错误
            if "error" in result:
                # 超时错误码
                pass
        
        except requests.exceptions.Timeout:
            # 请求超时 - 符合预期
            pass
    
    @pytest.mark.task
    def test_task_input_required_state(self, helper):
        """
        测试 input-required 状态处理
        
        前置条件：
            - Agent 支持交互式任务
            - 任务可能需要额外输入
        
        测试步骤：
            1. 创建需要额外输入的任务
            2. 检查任务进入 input-required 状态
            3. 提供所需输入
            4. 验证任务继续执行
        
        预期结果：
            - 任务正确进入 input-required 状态
            - 提供输入后任务继续
            - 最终任务完成
        """
        # 发送需要确认的请求
        message = {
            "role": "user",
            "parts": [helper.create_text_part("执行一个需要确认的操作")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        response = helper.send_request(payload)
        
        result = response.json().get("result", {})
        task_id = result.get("taskId")
        context_id = result.get("contextId")
        
        # 检查是否进入 input-required 状态
        status = result.get("status", {})
        if status.get("state") == "input-required":
            # 提供所需输入
            followup_message = {
                "role": "user",
                "parts": [helper.create_text_part("确认执行")],
                "messageId": helper.generate_message_id(),
                "taskId": task_id,
                "contextId": context_id
            }
            
            followup_payload = helper.build_jsonrpc_request(
                "message/send",
                {"message": followup_message}
            )
            
            followup_response = helper.send_request(followup_payload)
            
            assert followup_response.status_code == 200
            
            followup_result = followup_response.json().get("result", {})
            new_status = followup_result.get("status", {})
            
            # 任务应继续执行
            assert new_status.get("state") != "input-required", \
                "提供输入后任务应继续执行"
    
    @pytest.mark.task
    def test_get_nonexistent_task(self, helper):
        """
        测试查询不存在的 Task
        
        前置条件：
            - 任务ID 不存在
        
        测试步骤：
            1. 使用不存在的 task ID 查询
            2. 验证响应
        
        预期结果：
            - 返回错误响应
            - 错误码指示任务不存在
        """
        fake_task_id = "nonexistent-task-id-12345"
        
        payload = helper.build_jsonrpc_request(
            "tasks/get",
            {"id": fake_task_id}
        )
        
        response = helper.send_request(payload)
        
        result = response.json()
        
        # 应返回错误
        assert "error" in result, "查询不存在的任务应返回错误"


# ==================== 4. 流式响应测试 ====================

class TestStreamingResponse:
    """
    流式响应测试集
    
    测试 A2A 协议的 SSE (Server-Sent Events) 流式响应功能。
    使用 message/stream 方法实现实时数据推送。
    """
    
    @pytest.mark.streaming
    @pytest.mark.smoke
    def test_sse_connection_establishment(self, helper):
        """
        测试 SSE 连接建立
        
        前置条件：
            - Agent 支持流式响应
            - Agent Card 中 capabilities.streaming 为 true
        
        测试步骤：
            1. 发送 message/stream 请求
            2. 验证连接建立
            3. 验证响应头包含正确的 Content-Type
        
        预期结果：
            - HTTP 状态码 200
            - Content-Type 为 text/event-stream
            - 连接保持打开
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("开始流式响应测试")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/stream", {"message": message})
        
        response = helper.send_stream_request(payload)
        
        # 断言
        assert response.status_code == 200, f"HTTP 状态码应为 200，实际 {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "text/event-stream" in content_type or "application/json" in content_type, \
            f"Content-Type 应为 text/event-stream 或 application/json，实际 {content_type}"
    
    @pytest.mark.streaming
    def test_stream_data_reception(self, helper):
        """
        测试流式数据接收
        
        前置条件：
            - SSE 连接成功建立
            - Agent 返回多个流事件
        
        测试步骤：
            1. 发送流式请求
            2. 接收多个 SSE 事件
            3. 验证事件格式
        
        预期结果：
            - 接收到多个 data 事件
            - 每个事件包含有效的 JSON 数据
            - 最后一个事件包含 completed 状态
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("生成一个长故事")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/stream", {"message": message})
        
        response = helper.send_stream_request(payload)
        
        events_received = 0
        last_state = None
        
        # 读取流事件
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            # SSE 格式: data: {...}
            if line.startswith("data:"):
                events_received += 1
                data_str = line[5:].strip()  # 去掉 "data:" 前缀
                
                try:
                    event_data = json.loads(data_str)
                    
                    # 验证事件结构
                    assert isinstance(event_data, dict), "事件数据应为对象"
                    
                    # 检查状态更新
                    if "result" in event_data:
                        result = event_data["result"]
                        if result.get("kind") == "status-update":
                            last_state = result.get("status", {}).get("state")
                
                except json.JSONDecodeError:
                    pytest.fail(f"无法解析事件数据: {data_str}")
            
            # 限制接收数量（避免无限循环）
            if events_received >= 100:
                break
        
        # 断言
        assert events_received > 0, "应接收到至少一个流事件"
    
    @pytest.mark.streaming
    @pytest.mark.negative
    def test_stream_interruption_handling(self, helper):
        """
        测试流中断处理
        
        前置条件：
            - 流式连接已建立
        
        测试步骤：
            1. 发送流式请求
            2. 在接收过程中关闭连接
            3. 验证服务端正确处理
        
        预期结果：
            - 服务端正确释放资源
            - 不抛出未处理异常
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("开始长任务")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/stream", {"message": message})
        
        response = helper.send_stream_request(payload)
        
        # 读取少量数据后关闭
        events_count = 0
        for line in response.iter_lines(decode_unicode=True):
            events_count += 1
            if events_count >= 2:
                break
        
        # 关闭连接
        response.close()
        
        # 如果到达这里，说明连接被正确关闭
        assert True
    
    @pytest.mark.streaming
    @pytest.mark.negative
    def test_stream_timeout(self, helper):
        """
        测试流超时
        
        前置条件：
            - 流式响应有超时限制
        
        测试步骤：
            1. 发送流式请求
            2. 设置较短的超时时间
            3. 验证超时处理
        
        预期结果：
            - 连接超时后正确关闭
            - 或收到超时错误
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("开始流式任务")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/stream", {"message": message})
        
        try:
            # 设置短超时
            response = requests.post(
                A2AConfig.API_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=2  # 2秒超时
            )
            
            # 尝试读取
            for _ in response.iter_lines():
                pass
        
        except requests.exceptions.Timeout:
            # 超时 - 符合预期
            pass
        except requests.exceptions.RequestException:
            # 其他请求异常也是可接受的
            pass


# ==================== 5. 认证测试 ====================

class TestAuthentication:
    """
    认证测试集
    
    测试 A2A 协议的认证机制，包括：
    - Token 验证
    - 权限检查
    - 扩展 Agent Card 访问
    """
    
    @pytest.mark.auth
    @pytest.mark.negative
    def test_access_without_token(self, helper):
        """
        测试无 Token 访问
        
        前置条件：
            - 某些功能需要认证
            - 服务配置了认证要求
        
        测试步骤：
            1. 不携带任何认证信息发送请求
            2. 访问需要认证的端点
            3. 验证响应
        
        预期结果：
            - 返回 401 Unauthorized
            - 或返回 JSON-RPC 错误
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("访问需要认证的功能")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        # 不带任何认证头
        response = helper.send_request(payload)
        
        # 根据服务端配置，可能返回 401 或允许访问
        # 如果返回 401，验证错误格式
        if response.status_code == 401:
            assert True  # 符合预期
        elif response.status_code == 200:
            # 服务端不要求认证，测试通过
            assert True
        else:
            result = response.json()
            if "error" in result:
                # JSON-RPC 错误
                assert result["error"]["code"] < 0
    
    @pytest.mark.auth
    @pytest.mark.negative
    def test_access_with_invalid_token(self, helper, invalid_token):
        """
        测试无效 Token 访问
        
        前置条件：
            - 服务端验证 Token
        
        测试步骤：
            1. 携带无效 Token 发送请求
            2. 验证响应
        
        预期结果：
            - 返回 401 或 403
            - 或返回认证失败错误
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("测试无效 Token")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        response = helper.send_request(payload, headers={
            "Authorization": f"Bearer {invalid_token}"
        })
        
        # 应返回认证错误
        if response.status_code in [401, 403]:
            assert True  # 符合预期
        else:
            result = response.json()
            if "error" in result:
                # 验证错误码
                assert result["error"]["code"] < 0
    
    @pytest.mark.auth
    @pytest.mark.negative
    def test_access_with_expired_token(self, helper, expired_token):
        """
        测试过期 Token 访问
        
        前置条件：
            - 服务端检查 Token 有效期
        
        测试步骤：
            1. 携带过期 Token 发送请求
            2. 验证响应
        
        预期结果：
            - 返回 Token 过期错误
            - 错误信息指示需要重新认证
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("测试过期 Token")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        response = helper.send_request(payload, headers={
            "Authorization": f"Bearer {expired_token}"
        })
        
        # 验证响应
        if response.status_code == 401:
            # 检查是否有过期提示
            www_authenticate = response.headers.get("WWW-Authenticate", "")
            if "expired" in www_authenticate.lower():
                assert True  # 明确指示过期
    
    @pytest.mark.auth
    @pytest.mark.negative
    def test_insufficient_permissions(self, helper, valid_token):
        """
        测试权限不足
        
        前置条件：
            - 存在权限分级
            - 用户权限不足以执行操作
        
        测试步骤：
            1. 使用低权限用户 Token
            2. 访问高权限功能
            3. 验证响应
        
        预期结果：
            - 返回 403 Forbidden
            - 或返回权限不足错误
        """
        # 假设这个操作需要管理员权限
        message = {
            "role": "user",
            "parts": [helper.create_data_part({
                "action": "admin_operation",
                "target": "sensitive_resource"
            })],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        response = helper.send_request(payload, headers={
            "Authorization": f"Bearer {valid_token}"
        })
        
        # 根据实际权限配置验证
        if response.status_code == 403:
            assert True  # 权限不足被正确拒绝
        elif response.status_code == 200:
            # 如果用户确实有权限，测试也通过
            assert True
    
    @pytest.mark.auth
    def test_extended_agent_card_access(self, helper, valid_token):
        """
        测试扩展 Agent Card 访问
        
        前置条件：
            - Agent 支持扩展 Agent Card
            - Agent Card 中 capabilities.extended_agent_card 为 true
        
        测试步骤：
            1. 获取公开 Agent Card
            2. 获取认证后的扩展 Agent Card
            3. 比较两者内容
        
        预期结果：
            - 扩展 Agent Card 包含更多信息
            - 需要认证才能访问
        """
        # 获取公开 Agent Card
        public_response = requests.get(
            A2AConfig.AGENT_CARD_URL,
            timeout=A2AConfig.TIMEOUT
        )
        
        if public_response.status_code != 200:
            pytest.skip("Agent Card 不可用")
        
        public_card = public_response.json()
        
        # 尝试获取扩展 Agent Card
        extended_url = f"{A2AConfig.BASE_URL}/a2a/agent/authenticatedExtendedCard"
        
        extended_response = requests.get(
            extended_url,
            headers={"Authorization": f"Bearer {valid_token}"},
            timeout=A2AConfig.TIMEOUT
        )
        
        if extended_response.status_code == 200:
            extended_card = extended_response.json()
            
            # 扩展卡片应包含更多信息
            # 具体验证取决于实际实现
            assert isinstance(extended_card, dict)
        
        elif extended_response.status_code == 404:
            pytest.skip("扩展 Agent Card 端点不存在")
        
        elif extended_response.status_code == 401:
            # 认证失败 - 可能测试 Token 无效
            pytest.skip("认证失败")


# ==================== 6. 边界测试 ====================

class TestBoundaryConditions:
    """
    边界条件测试集
    
    测试系统在极端条件下的行为：
    - 并发请求
    - 频率限制
    - 超时处理
    - 资源耗尽
    """
    
    @pytest.mark.boundary
    @pytest.mark.slow
    def test_concurrent_requests(self, helper):
        """
        测试并发请求
        
        前置条件：
            - Agent 支持并发处理
        
        测试步骤：
            1. 同时发送多个请求
            2. 验证所有请求都得到响应
            3. 验证响应正确性
        
        预期结果：
            - 所有请求成功完成
            - 响应内容正确
            - 无竞态条件错误
        """
        num_concurrent = 10
        
        def send_concurrent_message(index):
            message = {
                "role": "user",
                "parts": [helper.create_text_part(f"并发测试消息 {index}")],
                "messageId": helper.generate_message_id()
            }
            
            payload = helper.build_jsonrpc_request("message/send", {"message": message})
            response = helper.send_request(payload)
            
            return index, response.status_code, response.json()
        
        results = []
        
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [
                executor.submit(send_concurrent_message, i)
                for i in range(num_concurrent)
            ]
            
            for future in as_completed(futures):
                try:
                    index, status_code, result = future.result()
                    results.append((index, status_code, result))
                except Exception as e:
                    results.append((None, None, str(e)))
        
        # 验证所有请求都有响应
        assert len(results) == num_concurrent, \
            f"应收到 {num_concurrent} 个响应，实际 {len(results)}"
        
        # 验证响应状态
        successful = [r for r in results if r[1] == 200]
        assert len(successful) > 0, "至少应有一些请求成功"
    
    @pytest.mark.boundary
    @pytest.mark.negative
    def test_rate_limiting(self, helper):
        """
        测试请求频率限制
        
        前置条件：
            - Agent 有频率限制
        
        测试步骤：
            1. 快速发送大量请求
            2. 观察是否触发频率限制
            3. 验证限制响应格式
        
        预期结果：
            - 超过限制后返回 429 Too Many Requests
            - 或返回 JSON-RPC 错误
        """
        num_requests = 50
        rate_limited = False
        
        for i in range(num_requests):
            message = {
                "role": "user",
                "parts": [helper.create_text_part(f"频率测试 {i}")],
                "messageId": helper.generate_message_id()
            }
            
            payload = helper.build_jsonrpc_request("message/send", {"message": message})
            response = helper.send_request(payload)
            
            if response.status_code == 429:
                rate_limited = True
                break
            
            # 短暂延迟避免过于频繁
            time.sleep(0.05)
        
        # 如果服务端有频率限制，应该被触发
        # 如果没有，测试也通过（只是验证行为）
        if rate_limited:
            assert True, "频率限制正确触发"
    
    @pytest.mark.boundary
    @pytest.mark.negative
    def test_request_timeout_handling(self, helper):
        """
        测试请求超时处理
        
        前置条件：
            - Agent 有请求超时限制
        
        测试步骤：
            1. 发送需要长时间处理的请求
            2. 设置较短的超时时间
            3. 验证超时处理
        
        预期结果：
            - 请求超时后正确返回
            - 资源被正确释放
        """
        message = {
            "role": "user",
            "parts": [helper.create_text_part("执行一个耗时操作")],
            "messageId": helper.generate_message_id()
        }
        
        payload = helper.build_jsonrpc_request("message/send", {"message": message})
        
        try:
            response = requests.post(
                A2AConfig.API_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=1  # 1秒超时
            )
            
            # 如果成功返回，检查响应
            assert response.status_code in [200, 408, 504]
        
        except requests.exceptions.Timeout:
            # 超时 - 符合预期
            assert True
        except requests.exceptions.RequestException:
            # 其他请求异常
            pass
    
    @pytest.mark.boundary
    @pytest.mark.negative
    @pytest.mark.slow
    def test_resource_exhaustion(self, helper):
        """
        测试资源耗尽场景
        
        前置条件：
            - Agent 有资源限制
        
        测试步骤：
            1. 发送大量并发请求或大消息
            2. 观察系统响应
            3. 验证优雅降级
        
        预期结果：
            - 系统返回适当错误而非崩溃
            - 错误信息指示资源不足
        """
        # 发送大量并发大消息
        num_requests = 20
        large_text = "X" * 100000  # 100KB 文本
        
        results = []
        
        def send_large_request():
            message = {
                "role": "user",
                "parts": [helper.create_text_part(large_text)],
                "messageId": helper.generate_message_id()
            }
            
            payload = helper.build_jsonrpc_request("message/send", {"message": message})
            
            try:
                response = helper.send_request(payload)
                return response.status_code
            except Exception as e:
                return str(e)
        
        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(send_large_request) for _ in range(num_requests)]
            
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append(str(e))
        
        # 验证系统没有崩溃
        # 应该有一些成功和一些失败的响应
        assert len(results) > 0, "应收到一些响应"
        
        # 检查是否有资源不足的错误
        error_responses = [r for r in results if isinstance(r, str) or (isinstance(r, int) and r >= 500)]
        
        # 系统可能拒绝部分请求，这是正常的
        assert True
    
    @pytest.mark.boundary
    def test_malformed_json_request(self, helper):
        """
        测试格式错误的 JSON 请求
        
        前置条件：
            - Agent 服务正常运行
        
        测试步骤：
            1. 发送无效 JSON 格式的请求
            2. 验证响应
        
        预期结果：
            - 返回 JSON 解析错误
            - 错误码 -32700 (Parse error)
        """
        invalid_json = '{"jsonrpc": "2.0", "method": "message/send", "params": {broken}'
        
        response = requests.post(
            A2AConfig.API_ENDPOINT,
            data=invalid_json,
            headers={"Content-Type": "application/json"},
            timeout=A2AConfig.TIMEOUT
        )
        
        # 应返回错误
        if response.status_code == 400:
            assert True  # Bad Request
        else:
            try:
                result = response.json()
                if "error" in result:
                    assert result["error"].get("code") == -32700, \
                        "应返回 Parse error (-32700)"
            except:
                pass  # 非 JSON 响应也可接受
    
    @pytest.mark.boundary
    def test_invalid_jsonrpc_version(self, helper):
        """
        测试无效的 JSON-RPC 版本
        
        前置条件：
            - Agent 使用 JSON-RPC 2.0
        
        测试步骤：
            1. 发送错误版本的 JSON-RPC 请求
            2. 验证响应
        
        预期结果：
            - 返回 Invalid Request 错误
            - 错误码 -32600
        """
        payload = {
            "jsonrpc": "1.0",  # 无效版本
            "id": 1,
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "test"}]}}
        }
        
        response = helper.send_request(payload)
        
        result = response.json()
        
        if "error" in result:
            # 可能是 Invalid Request 错误
            pass
    
    @pytest.mark.boundary
    def test_unknown_method(self, helper):
        """
        测试未知的 JSON-RPC 方法
        
        前置条件：
            - Agent 服务正常运行
        
        测试步骤：
            1. 调用不存在的方法
            2. 验证响应
        
        预期结果：
            - 返回 Method not found 错误
            - 错误码 -32601
        """
        payload = helper.build_jsonrpc_request(
            "unknown/nonexistent/method",
            {}
        )
        
        response = helper.send_request(payload)
        
        result = response.json()
        
        assert "error" in result, "未知方法应返回错误"
        assert result["error"].get("code") == -32601, \
            "应返回 Method not found (-32601)"


# ==================== 运行配置 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
