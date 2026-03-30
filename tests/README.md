# A2A 协议测试用例库

全面的测试用例集，覆盖 A2A 协议的所有核心功能和边界场景。

## 测试类别

### 1. Agent Card 测试 (`TestAgentCard`)
- ✅ 正常获取 Agent Card
- ✅ Agent Card 必填字段验证
- ✅ Agent Card 不存在
- ✅ Agent Card 格式错误
- ✅ Agent Card 缺少必填字段
- ✅ Agent Card 版本验证
- ✅ Agent Card capabilities 结构验证

### 2. 消息发送测试 (`TestMessageSend`)
- ✅ 简单文本消息
- ✅ 多轮对话
- ✅ 文件传输
- ✅ 结构化数据
- ✅ 空消息
- ✅ 超大消息
- ✅ 无效 Part 类型
- ✅ 带 contextId 的消息

### 3. Task 生命周期测试 (`TestTaskLifecycle`)
- ✅ Task 创建
- ✅ Task 状态转换
- ✅ Task 取消
- ✅ Task 超时
- ✅ input-required 状态处理
- ✅ 查询不存在的 Task

### 4. 流式响应测试 (`TestStreamingResponse`)
- ✅ SSE 连接建立
- ✅ 流式数据接收
- ✅ 流中断处理
- ✅ 流超时

### 5. 认证测试 (`TestAuthentication`)
- ✅ 无 Token 访问
- ✅ 无效 Token
- ✅ 过期 Token
- ✅ 权限不足
- ✅ 扩展 Agent Card 访问

### 6. 边界测试 (`TestBoundaryConditions`)
- ✅ 并发请求
- ✅ 请求频率限制
- ✅ 超时处理
- ✅ 资源耗尽
- ✅ 格式错误的 JSON 请求
- ✅ 无效的 JSON-RPC 版本
- ✅ 未知方法调用

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行测试

```bash
# 运行所有测试
pytest test_cases.py -v

# 运行特定类别
pytest test_cases.py -k "agent_card" -v
pytest test_cases.py -k "message" -v
pytest test_cases.py -k "task" -v
pytest test_cases.py -k "streaming" -v
pytest test_cases.py -k "auth" -v
pytest test_cases.py -k "boundary" -v

# 运行冒烟测试
pytest test_cases.py -m smoke -v

# 运行负面测试
pytest test_cases.py -m negative -v

# 包含慢速测试
pytest test_cases.py --runslow -v

# 带覆盖率报告
pytest test_cases.py --cov=. --cov-report=html

# 指定服务 URL
pytest test_cases.py --base-url=http://localhost:3000 -v
```

## 测试结构

每个测试用例包含：
- **测试描述**: 清晰的测试目的说明
- **前置条件**: 测试执行所需的条件
- **测试步骤**: 详细的操作步骤
- **预期结果**: 预期的行为和输出
- **断言**: 验证测试结果的断言语句

## 配置

测试配置位于 `test_cases.py` 中的 `A2AConfig` 类：

```python
class A2AConfig:
    BASE_URL = "http://localhost:8000"
    AGENT_CARD_URL = f"{BASE_URL}/.well-known/agent.json"
    API_ENDPOINT = f"{BASE_URL}/"
    TIMEOUT = 30
    MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
    VALID_TOKEN = "valid-test-token"
    EXPIRED_TOKEN = "expired-test-token"
    INVALID_TOKEN = "invalid-test-token"
```

## 标记说明

| 标记 | 说明 |
|------|------|
| `@pytest.mark.smoke` | 核心冒烟测试 |
| `@pytest.mark.negative` | 负面测试（错误处理） |
| `@pytest.mark.slow` | 慢速测试（需要 `--runslow`） |
| `@pytest.mark.agent_card` | Agent Card 相关 |
| `@pytest.mark.message` | 消息发送相关 |
| `@pytest.mark.task` | Task 生命周期 |
| `@pytest.mark.streaming` | 流式响应 |
| `@pytest.mark.auth` | 认证相关 |
| `@pytest.mark.boundary` | 边界条件 |

## 注意事项

1. **服务依赖**: 大部分测试需要 A2A Agent 服务运行中
2. **认证测试**: 需要 `requests-mock` 或真实的认证服务
3. **并发测试**: 可能对服务造成压力，谨慎在生产环境运行
4. **慢速测试**: 默认跳过，使用 `--runslow` 启用

## 最佳实践

1. 先运行冒烟测试验证基本功能
2. 使用 `-k` 参数过滤特定测试类别
3. 开发时使用 `-x` 参数在第一个失败时停止
4. CI/CD 中排除慢速测试
5. 使用覆盖率报告监控测试覆盖率

## 故障排除

### 导入错误
```bash
pip install pytest pytest-cov requests requests-mock
```

### 连接拒绝
确保 A2A Agent 服务正在运行：
```bash
# 检查服务状态
curl http://localhost:8000/.well-known/agent.json
```

### 测试跳过
检查服务配置是否满足前置条件，部分测试会自动跳过不支持的特性。
