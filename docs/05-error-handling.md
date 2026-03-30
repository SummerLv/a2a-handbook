# A2A 异常处理指南

> 三层异常模型：HTTP 层 → JSON-RPC 层 → 业务层

---

## 📚 快速导航

- [HTTP 层异常](#1-http-层异常)
- [JSON-RPC 层异常](#2-json-rpc-层异常)
- [业务层异常](#3-业务层异常)
- [错误处理最佳实践](#4-错误处理最佳实践)

---

## 1. HTTP 层异常

HTTP 层异常发生在 JSON-RPC 处理之前，通常由网络、认证或服务器状态引起。

### 1.1 常见 HTTP 错误码

| 状态码 | 名称 | 原因 | 处理策略 |
|--------|------|------|----------|
| **400** | Bad Request | 请求格式错误 | 检查 Content-Type、请求体 |
| **401** | Unauthorized | 认证失败 | 刷新 Token 或重新登录 |
| **403** | Forbidden | 权限不足 | 不重试，提示申请权限 |
| **404** | Not Found | 资源不存在 | 检查 ID 拼写或重新创建 |
| **429** | Rate Limit | 请求频率超限 | 等待 `Retry-After` 后重试 |
| **500** | Internal Error | 服务器内部错误 | 指数退避重试，最多 3 次 |
| **502** | Bad Gateway | 上游服务不可用 | 切换 Agent 或重试 |
| **503** | Service Unavailable | 服务维护中 | 等待后重试 |

### 1.2 关键处理代码

```typescript
// 统一 HTTP 错误处理
async function handleResponse(response: Response): Promise<JsonRpcResponse> {
  if (!response.ok) {
    const error = await response.json();
    
    // Rate Limit 特殊处理
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      throw new A2ARateLimitError(retryAfter);
    }
    
    throw new A2AHttpError(response.status, error.message);
  }
  
  return response.json();
}
```

---

## 2. JSON-RPC 层异常

JSON-RPC 错误在请求被解析后发生，是 A2A 协议的核心错误类型。

### 2.1 标准 JSON-RPC 错误码

| 错误码 | 名称 | 说明 | 处理建议 |
|--------|------|------|----------|
| **-32700** | Parse Error | JSON 解析失败 | 验证 JSON 有效性 |
| **-32600** | Invalid Request | 请求结构不合规 | 检查必填字段 |
| **-32601** | Method Not Found | 方法不存在 | 验证 Agent Card 能力 |
| **-32602** | Invalid Params | 参数无效 | 使用 JSON Schema 验证 |
| **-32603** | Internal Error | 服务器内部错误 | 重试或联系服务方 |

### 2.2 A2A 特定错误码 (-32001 到 -32010)

| 错误码 | 名称 | 场景 |
|--------|------|------|
| **-32001** | TaskNotFound | taskId 不存在 |
| **-32002** | TaskCancelled | 任务已被取消 |
| **-32003** | TaskExpired | 任务已过期 |
| **-32004** | InvalidContext | contextId 无效 |
| **-32005** | MessageConflict | messageId 冲突 |
| **-32006** | PartProcessingError | Part 处理失败 |
| **-32007** | FileTooLarge | 文件超出限制 |
| **-32008** | UnsupportedFormat | 格式不支持 |
| **-32009** | AgentUnavailable | Agent 不可用 |
| **-32010** | CapabilityNotSupported | 能力不支持 |

### 2.3 错误响应格式

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "violations": [
        { "path": "task.id", "message": "Invalid UUID format" }
      ]
    }
  },
  "id": "req-123"
}
```

### 2.4 参数验证示例

```typescript
import Ajv from 'ajv';

const ajv = new Ajv({ allErrors: true });

function validateParams(schema: object, params: unknown): void {
  const validate = ajv.compile(schema);
  if (!validate(params)) {
    throw new A2AValidationError('Invalid parameters', validate.errors);
  }
}
```

---

## 3. 业务层异常

业务层异常涉及 Task、Message、Part 等核心实体的状态问题。

### 3.1 Task 状态异常

| 状态 | 含义 | 处理方式 |
|------|------|----------|
| **cancelled** | 任务已取消 | 清理资源，可创建新任务 |
| **failed** | 任务失败 | 检查错误消息，可重试 |
| **expired** | 任务过期 | 重新创建任务 |

```typescript
// 处理失败任务
async function handleFailedTask(task: Task): Promise<Task | null> {
  if (task.status.state !== 'failed') return null;
  
  const errorMsg = task.status.message?.parts
    ?.filter(p => p.type === 'text')
    .map(p => p.text)
    .join('\n') || 'Unknown error';
  
  console.error(`Task ${task.id} failed: ${errorMsg}`);
  
  // 判断是否可重试
  if (isRetryable(errorMsg)) {
    return recreateTask(task);
  }
  
  return null;
}
```

### 3.2 常见业务异常

#### contextId 无效或过期

```typescript
class ContextManager {
  private ttlHours = 24;
  
  async getValidContext(contextId?: string): Promise<string> {
    if (contextId && !this.isExpired(contextId)) {
      return contextId;
    }
    return this.createContext();
  }
}
```

#### messageId 冲突（幂等性处理）

```typescript
class IdempotentSender {
  private cache = new Map<string, Task>();
  
  async send(message: Message, taskId: string): Promise<Task> {
    const id = message.messageId || generateId();
    
    if (this.cache.has(id)) {
      return this.cache.get(id)!;
    }
    
    try {
      const task = await client.send({ ...message, messageId: id });
      this.cache.set(id, task);
      return task;
    } catch (e) {
      if (e.code === -32005) { // MessageConflict
        return this.cache.get(id) || await getTask(taskId);
      }
      throw e;
    }
  }
}
```

#### Part 解析失败

```typescript
function validatePart(part: Part): void {
  if (part.type === 'text' && !part.text?.trim()) {
    throw new Error('Text part cannot be empty');
  }
  
  if (part.type === 'file' && part.file?.bytes) {
    try {
      Buffer.from(part.file.bytes, 'base64');
    } catch {
      throw new Error('Invalid base64 encoding');
    }
  }
}
```

---

## 4. 错误处理最佳实践

### 4.1 错误分类与策略

| 错误类型 | 可重试 | 处理策略 |
|----------|--------|----------|
| 网络错误 | ✅ | 指数退避重试 |
| 认证错误 | ⚠️ | 仅 Token 过期可刷新 |
| 验证错误 | ❌ | 修正参数后重新请求 |
| 服务端错误 | ✅ | 最多重试 3 次 |
| 业务状态错误 | ❌ | 根据具体错误处理 |

### 4.2 重试策略

```typescript
interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryableStatuses: number[];
}

const DEFAULT_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 30000,
  retryableStatuses: [408, 429, 500, 502, 503, 504]
};

async function requestWithRetry(
  url: string,
  body: unknown,
  config = DEFAULT_CONFIG
): Promise<Response> {
  for (let attempt = 0; attempt < config.maxRetries; attempt++) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    
    if (response.ok || !config.retryableStatuses.includes(response.status)) {
      return response;
    }
    
    // Rate Limit 使用 Retry-After
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
      await sleep(retryAfter * 1000);
    } else {
      // 指数退避 + 抖动
      const delay = Math.min(
        config.baseDelay * Math.pow(2, attempt) + Math.random() * 1000,
        config.maxDelay
      );
      await sleep(delay);
    }
  }
  
  throw new Error('Max retries exceeded');
}
```

### 4.3 统一错误处理中间件

```typescript
class ErrorHandler {
  classify(error: unknown): { type: string; retryable: boolean; message: string } {
    if (error instanceof A2ANetworkError) {
      return { type: 'network', retryable: true, message: '网络连接失败' };
    }
    if (error instanceof A2AAuthError) {
      return { type: 'auth', retryable: error.isTokenExpired, message: '认证失败' };
    }
    if (error instanceof A2AValidationError) {
      return { type: 'validation', retryable: false, message: '参数错误' };
    }
    return { type: 'unknown', retryable: false, message: '未知错误' };
  }
}
```

### 4.4 客户端最佳实践

**✅ 推荐做法**

- 发送前验证请求格式
- 使用 messageId 实现幂等性
- 实现请求超时控制（连接 5s，读取 30s）
- 记录 request_id 用于问题追踪
- 为用户提供友好的错误提示

**❌ 避免做法**

- 无限重试
- 忽略 429 Rate Limit
- 对认证错误重试
- 硬编码超时时间

---

## 📖 详细参考

完整的错误码列表、代码示例和边缘情况处理，请参阅：
- [错误码参考手册](../.agents/skills/a2a-handbook/references/error-codes.md)

---

## 下一步

- 💻 [代码示例](03-examples.md) - 查看完整实现
- 🎯 [场景全景](05-scenarios.md) - 了解典型使用场景
- 📝 [故障排查](08-troubleshooting.md) - 常见问题解决
