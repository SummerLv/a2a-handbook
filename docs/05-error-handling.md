# A2A 异常场景处理指南

本文档详细描述 A2A 协议中可能出现的各类异常场景，包括错误识别、响应格式和最佳处理实践。

---

## 目录

1. [HTTP 层异常](#1-http-层异常)
2. [JSON-RPC 层异常](#2-json-rpc-层异常)
3. [业务层异常](#3-业务层异常)
4. [边界情况](#4-边界情况)
5. [通用错误处理模式](#5-通用错误处理模式)

---

## 1. HTTP 层异常

HTTP 层异常发生在请求到达 JSON-RPC 处理层之前，通常由网络、认证或服务器状态问题引起。

### 1.1 400 Bad Request

#### 问题描述
请求格式不正确，服务器无法理解请求内容。常见原因：
- Content-Type 头缺失或错误
- 请求体为空
- HTTP 方法不支持

#### 错误响应示例

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": 400,
    "message": "Invalid request: Content-Type must be application/json",
    "details": {
      "received": "text/plain",
      "expected": "application/json"
    }
  }
}
```

#### 处理建议

1. **客户端检查**
   - 确保 Content-Type 设置正确
   - 验证请求体不为空
   - 检查 HTTP 方法是否正确（A2A 使用 POST）

2. **服务端实现**
   - 尽早验证请求头
   - 返回详细的错误信息帮助调试

#### 代码示例

```typescript
// 客户端处理
async function safeRequest(url: string, body: unknown) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  if (response.status === 400) {
    const error = await response.json();
    throw new A2ARequestError(error.message, error.details);
  }
  
  return response;
}

class A2ARequestError extends Error {
  constructor(
    message: string,
    public details: Record<string, unknown>
  ) {
    super(message);
    this.name = 'A2ARequestError';
  }
}
```

---

### 1.2 401 Unauthorized

#### 问题描述
请求缺少有效的身份认证信息。A2A 协议通常使用以下认证方式：
- Bearer Token
- API Key
- 签名验证

#### 错误响应示例

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="A2A", error="invalid_token"
Content-Type: application/json

{
  "error": {
    "code": 401,
    "message": "Authentication required",
    "details": {
      "auth_type": "Bearer",
      "error_description": "Token expired"
    }
  }
}
```

#### 处理建议

1. **Token 过期处理**
   - 检查 `WWW-Authenticate` 头中的错误原因
   - 如支持刷新令牌，自动刷新后重试
   - 否则提示用户重新认证

2. **重试策略**
   - 仅在可刷新凭证时重试
   - 避免无限重试导致锁定

#### 代码示例

```typescript
class A2AClient {
  private token: string;
  private refreshToken: string;
  
  async request(method: string, params: unknown) {
    const response = await this.sendRequest(method, params);
    
    if (response.status === 401) {
      const error = await response.json();
      
      // 尝试刷新 token
      if (error.details?.error_description === 'Token expired') {
        const refreshed = await this.refreshAccessToken();
        if (refreshed) {
          return this.sendRequest(method, params);
        }
      }
      
      throw new A2AAuthError('Authentication failed', error);
    }
    
    return response;
  }
  
  private async refreshAccessToken(): Promise<boolean> {
    try {
      const response = await fetch('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: this.refreshToken })
      });
      
      if (response.ok) {
        const data = await response.json();
        this.token = data.access_token;
        return true;
      }
    } catch (e) {
      console.error('Token refresh failed:', e);
    }
    return false;
  }
}
```

---

### 1.3 403 Forbidden

#### 问题描述
请求已认证，但用户/Agent 没有执行该操作的权限。常见场景：
- 访问其他 Agent 的私有资源
- 执行超出权限范围的操作
- IP 被限制

#### 错误响应示例

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "error": {
    "code": 403,
    "message": "Access denied",
    "details": {
      "reason": "agent_not_authorized",
      "resource": "task:abc123",
      "required_permission": "task:write"
    }
  }
}
```

#### 处理建议

1. **权限不足**
   - 不要重试，请求不可能成功
   - 记录权限需求，提示用户或管理员
   - 考虑请求临时权限提升

2. **资源隔离**
   - 检查是否尝试访问其他 Agent 的资源
   - 使用正确的 contextId

#### 代码示例

```typescript
async function handleForbidden(response: Response) {
  const error = await response.json();
  
  switch (error.details?.reason) {
    case 'agent_not_authorized':
      console.warn(`Permission denied: need ${error.details.required_permission}`);
      // 可能需要通知用户申请权限
      throw new A2APermissionError(
        `Missing permission: ${error.details.required_permission}`
      );
      
    case 'resource_not_shared':
      // 资源未共享，检查 contextId
      throw new A2AResourceError('Resource not accessible in current context');
      
    default:
      throw new A2AForbiddenError(error.message);
  }
}
```

---

### 1.4 404 Not Found

#### 问题描述
请求的资源不存在。A2A 场景中常见于：
- Task 不存在
- Agent 端点未注册
- Message 不存在

#### 错误响应示例

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "error": {
    "code": 404,
    "message": "Resource not found",
    "details": {
      "resource_type": "task",
      "resource_id": "task_abc123"
    }
  }
}
```

#### 处理建议

1. **Task 不存在**
   - 检查 taskId 拼写
   - 可能已被删除或过期
   - 重新创建 Task

2. **Agent 端点不存在**
   - 检查 Agent URL 配置
   - 验证 Agent 是否已注册

#### 代码示例

```typescript
async function getTask(taskId: string): Promise<Task> {
  const response = await fetch(`/tasks/${taskId}`);
  
  if (response.status === 404) {
    // Task 不存在，可能需要重新创建
    console.warn(`Task ${taskId} not found, creating new one...`);
    return createNewTask();
  }
  
  return response.json();
}

// Agent 端点检查
async function discoverAgent(agentUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${agentUrl}/.well-known/a2a.json`);
    return response.ok;
  } catch {
    return false;
  }
}
```

---

### 1.5 429 Rate Limit

#### 问题描述
请求频率超过限制。A2A 服务通常对以下维度限流：
- 每秒请求数 (RPS)
- 每分钟请求数
- 并发连接数

#### 错误响应示例

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1711717200
Content-Type: application/json

{
  "error": {
    "code": 429,
    "message": "Rate limit exceeded",
    "details": {
      "limit": 100,
      "window": "1m",
      "retry_after": 60
    }
  }
}
```

#### 处理建议

1. **使用 Retry-After 头**
   - 解析 `Retry-After` 值（秒数或日期）
   - 等待指定时间后重试

2. **实现客户端限流**
   - 跟踪 `X-RateLimit-Remaining`
   - 实现请求队列和节流

#### 代码示例

```typescript
class RateLimitedClient {
  private queue: Array<() => Promise<void>> = [];
  private isProcessing = false;
  private remaining = 100;
  
  async request(method: string, params: unknown): Promise<Response> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const response = await this.sendRequest(method, params);
          
          // 更新限流状态
          this.remaining = parseInt(
            response.headers.get('X-RateLimit-Remaining') || '100'
          );
          
          if (response.status === 429) {
            const retryAfter = parseInt(
              response.headers.get('Retry-After') || '60'
            );
            // 等待后重新入队
            await sleep(retryAfter * 1000);
            resolve(this.request(method, params));
          } else {
            resolve(response);
          }
        } catch (e) {
          reject(e);
        }
      });
      
      this.processQueue();
    });
  }
  
  private async processQueue() {
    if (this.isProcessing || this.queue.length === 0) return;
    
    this.isProcessing = true;
    
    while (this.queue.length > 0) {
      if (this.remaining <= 5) {
        // 接近限制，等待
        await sleep(1000);
      }
      
      const task = this.queue.shift();
      await task!();
    }
    
    this.isProcessing = false;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

---

### 1.6 500 Internal Server Error

#### 问题描述
服务器内部错误，通常是未捕获的异常。客户端无法修复，只能重试或报告。

#### 错误响应示例

```http
HTTP/1.1 500 Internal Server Error
Content-Type: application/json

{
  "error": {
    "code": 500,
    "message": "Internal server error",
    "request_id": "req_abc123xyz"
  }
}
```

#### 处理建议

1. **重试策略**
   - 实现指数退避重试
   - 最多重试 3 次

2. **错误报告**
   - 保存 `request_id` 用于排查
   - 联系服务提供方

#### 代码示例

```typescript
async function requestWithRetry(
  url: string,
  body: unknown,
  maxRetries = 3
): Promise<Response> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      if (response.status === 500) {
        const error = await response.json();
        const requestId = error.request_id;
        console.error(`Server error (request_id: ${requestId}), attempt ${attempt + 1}`);
        
        if (attempt < maxRetries - 1) {
          await exponentialBackoff(attempt);
          continue;
        }
        
        throw new A2AServerError(
          `Server error after ${maxRetries} attempts`,
          requestId
        );
      }
      
      return response;
    } catch (e) {
      lastError = e as Error;
      if (attempt < maxRetries - 1) {
        await exponentialBackoff(attempt);
      }
    }
  }
  
  throw lastError;
}

function exponentialBackoff(attempt: number, baseDelay = 1000): Promise<void> {
  const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 1000;
  return sleep(delay);
}
```

---

### 1.7 502 Bad Gateway

#### 问题描述
网关或代理服务器从上游收到无效响应。A2A Agent 架构中常见于：
- Agent 服务不可用
- 网关配置错误
- 上游超时

#### 错误响应示例

```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json

{
  "error": {
    "code": 502,
    "message": "Bad Gateway",
    "details": {
      "upstream": "agent-service-1",
      "error": "connection_refused"
    }
  }
}
```

#### 处理建议

1. **临时性故障**
   - 等待后重试
   - 检查 Agent 服务状态

2. **持久性问题**
   - 联系管理员
   - 切换到备用 Agent

#### 代码示例

```typescript
class AgentPool {
  private agents: string[];
  private currentIndex = 0;
  
  async request(method: string, params: unknown): Promise<Response> {
    const maxAttempts = this.agents.length;
    
    for (let i = 0; i < maxAttempts; i++) {
      const agentUrl = this.agents[this.currentIndex];
      this.currentIndex = (this.currentIndex + 1) % this.agents.length;
      
      try {
        const response = await fetch(`${agentUrl}/rpc`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method, params })
        });
        
        if (response.status !== 502) {
          return response;
        }
        
        console.warn(`Agent ${agentUrl} returned 502, trying next...`);
      } catch (e) {
        console.warn(`Agent ${agentUrl} unreachable:`, e);
      }
    }
    
    throw new A2AError('All agents unavailable');
  }
}
```

---

### 1.8 503 Service Unavailable

#### 问题描述
服务暂时不可用，通常是因为维护或过载。

#### 错误响应示例

```http
HTTP/1.1 503 Service Unavailable
Retry-After: 300
Content-Type: application/json

{
  "error": {
    "code": 503,
    "message": "Service temporarily unavailable",
    "details": {
      "reason": "maintenance",
      "estimated_duration": "5 minutes"
    }
  }
}
```

#### 处理建议

1. **检查 Retry-After**
   - 遵守服务端建议的等待时间

2. **实现优雅降级**
   - 使用缓存数据
   - 显示维护提示

#### 代码示例

```typescript
async function requestWithMaintenanceHandling(
  url: string,
  body: unknown
): Promise<Response> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  
  if (response.status === 503) {
    const error = await response.json();
    const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
    
    if (error.details?.reason === 'maintenance') {
      console.info(`Service in maintenance, retry after ${retryAfter}s`);
      // 可以通知用户或使用缓存
    }
    
    // 等待后重试
    await sleep(retryAfter * 1000);
    return requestWithMaintenanceHandling(url, body);
  }
  
  return response;
}
```

---

### 1.9 超时处理

#### 问题描述
请求未在规定时间内完成。A2A 场景中常见：
- 连接超时（网络问题）
- 读取超时（处理缓慢）
- Agent 响应超时（长任务）

#### 处理建议

1. **设置合理超时**
   - 短请求：5-30 秒
   - 文件上传：根据大小调整
   - Agent 处理：使用异步模式

2. **区分超时类型**
   - 连接超时：网络问题，重试
   - 读取超时：任务可能在进行中，查询状态

#### 代码示例

```typescript
interface TimeoutOptions {
  connectTimeout?: number;  // 连接超时（毫秒）
  readTimeout?: number;     // 读取超时（毫秒）
}

async function requestWithTimeout(
  url: string,
  body: unknown,
  options: TimeoutOptions = {}
): Promise<Response> {
  const {
    connectTimeout = 5000,
    readTimeout = 30000
  } = options;
  
  const controller = new AbortController();
  
  // 连接超时
  const connectTimer = setTimeout(() => {
    controller.abort(new DOMException('Connection timeout', 'TimeoutError'));
  }, connectTimeout);
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal
    });
    
    clearTimeout(connectTimer);
    
    // 读取超时
    const readTimer = setTimeout(() => {
      controller.abort(new DOMException('Read timeout', 'TimeoutError'));
    }, readTimeout);
    
    return response;
    
  } catch (e) {
    if (e instanceof DOMException && e.name === 'TimeoutError') {
      if (e.message === 'Connection timeout') {
        throw new A2ATimeoutError('Connection timeout', 'connect');
      } else {
        // 读取超时 - 任务可能仍在进行
        throw new A2ATimeoutError(
          'Response timeout - task may still be processing',
          'read'
        );
      }
    }
    throw e;
  }
}

class A2ATimeoutError extends Error {
  constructor(
    message: string,
    public type: 'connect' | 'read'
  ) {
    super(message);
    this.name = 'A2ATimeoutError';
  }
}
```

---

### 1.10 重试策略最佳实践

#### 综合重试实现

```typescript
interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryableStatuses: number[];
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 30000,
  retryableStatuses: [408, 429, 500, 502, 503, 504]
};

async function robustRequest(
  url: string,
  body: unknown,
  config: Partial<RetryConfig> = {}
): Promise<Response> {
  const cfg = { ...DEFAULT_RETRY_CONFIG, ...config };
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < cfg.maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      // 成功响应
      if (response.ok) {
        return response;
      }
      
      // 不可重试的状态码
      if (!cfg.retryableStatuses.includes(response.status)) {
        return response; // 让调用者处理
      }
      
      // 429 特殊处理
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        if (retryAfter) {
          await sleep(parseInt(retryAfter) * 1000);
          continue;
        }
      }
      
      // 指数退避
      await sleep(calculateDelay(attempt, cfg.baseDelay, cfg.maxDelay));
      
    } catch (e) {
      lastError = e as Error;
      
      // 网络错误，重试
      if (attempt < cfg.maxRetries - 1) {
        await sleep(calculateDelay(attempt, cfg.baseDelay, cfg.maxDelay));
      }
    }
  }
  
  throw lastError || new A2AError('Max retries exceeded');
}

function calculateDelay(
  attempt: number,
  baseDelay: number,
  maxDelay: number
): number {
  const delay = baseDelay * Math.pow(2, attempt);
  const jitter = Math.random() * 1000;
  return Math.min(delay + jitter, maxDelay);
}
```

---

## 2. JSON-RPC 层异常

JSON-RPC 层异常发生在请求被解析和路由后，是 A2A 协议的核心错误类型。

### 2.1 -32700 Parse Error

#### 问题描述
服务器无法解析请求体为有效的 JSON。常见原因：
- JSON 语法错误（缺少引号、括号不匹配）
- 编码问题（非 UTF-8）
- 请求体被截断

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32700,
    "message": "Parse error",
    "data": {
      "position": 42,
      "expected": "string",
      "received": "EOF"
    }
  },
  "id": null
}
```

#### 处理建议

1. **客户端调试**
   - 在发送前验证 JSON 有效性
   - 使用 JSON.stringify() 确保正确编码

2. **日志记录**
   - 记录原始请求体用于调试
   - 注意敏感数据脱敏

#### 代码示例

```typescript
// 发送前验证
function safeStringify(data: unknown): string {
  try {
    const json = JSON.stringify(data);
    
    // 验证可以被解析回来
    JSON.parse(json);
    
    return json;
  } catch (e) {
    if (e instanceof TypeError) {
      throw new A2ASerializationError(
        `Cannot serialize: ${e.message}`
      );
    }
    throw new A2AParseError(`Invalid JSON structure: ${(e as Error).message}`);
  }
}

// 解析响应
function parseResponse(text: string): JsonRpcResponse {
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new A2AParseError(
      `Failed to parse response: ${(e as Error).message}`,
      text
    );
  }
}

class A2AParseError extends Error {
  constructor(
    message: string,
    public raw?: string
  ) {
    super(message);
    this.name = 'A2AParseError';
  }
}
```

---

### 2.2 -32600 Invalid Request

#### 问题描述
请求对象不符合 JSON-RPC 2.0 规范。常见问题：
- 缺少必填字段（jsonrpc, method）
- jsonrpc 版本不是 "2.0"
- id 类型不正确
- params 类型不正确（必须是对象或数组）

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {
      "violations": [
        {
          "field": "jsonrpc",
          "expected": "2.0",
          "received": "1.0"
        },
        {
          "field": "params",
          "expected": "object or array",
          "received": "string"
        }
      ]
    }
  },
  "id": null
}
```

#### 处理建议

1. **客户端验证**
   - 发送前验证请求结构
   - 使用类型检查（TypeScript）

2. **服务端实现**
   - 返回详细的违规信息
   - 逐个检查必填字段

#### 代码示例

```typescript
interface JsonRpcRequest {
  jsonrpc: '2.0';
  method: string;
  params?: Record<string, unknown> | unknown[];
  id?: string | number | null;
}

function validateRequest(request: unknown): JsonRpcRequest {
  if (typeof request !== 'object' || request === null) {
    throw new A2AInvalidRequestError('Request must be an object');
  }
  
  const req = request as Record<string, unknown>;
  const violations: Array<{ field: string; message: string }> = [];
  
  // 检查 jsonrpc
  if (req.jsonrpc !== '2.0') {
    violations.push({
      field: 'jsonrpc',
      message: `Expected "2.0", received ${JSON.stringify(req.jsonrpc)}`
    });
  }
  
  // 检查 method
  if (typeof req.method !== 'string' || req.method.length === 0) {
    violations.push({
      field: 'method',
      message: 'Method must be a non-empty string'
    });
  }
  
  // 检查 params（如果存在）
  if (req.params !== undefined) {
    if (typeof req.params !== 'object' || Array.isArray(req.params)) {
      // 数组是允许的
      if (!Array.isArray(req.params) || typeof req.params !== 'object') {
        violations.push({
          field: 'params',
          message: 'Params must be an object or array'
        });
      }
    }
  }
  
  // 检查 id（如果存在）
  if (req.id !== undefined && req.id !== null) {
    if (typeof req.id !== 'string' && typeof req.id !== 'number') {
      violations.push({
        field: 'id',
        message: 'Id must be string, number, or null'
      });
    }
  }
  
  if (violations.length > 0) {
    throw new A2AInvalidRequestError('Invalid request structure', violations);
  }
  
  return req as JsonRpcRequest;
}

class A2AInvalidRequestError extends Error {
  constructor(
    message: string,
    public violations?: Array<{ field: string; message: string }>
  ) {
    super(message);
    this.name = 'A2AInvalidRequestError';
  }
}
```

---

### 2.3 -32601 Method Not Found

#### 问题描述
请求的方法不存在或不支持。A2A 场景中常见：
- 方法名拼写错误
- Agent 不支持该能力
- 版本不匹配

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": {
      "method": "tasks/sendMesage",
      "suggestion": "Did you mean tasks/sendMessage?",
      "available_methods": [
        "tasks/send",
        "tasks/sendSubscribe",
        "tasks/get",
        "tasks/cancel"
      ]
    }
  },
  "id": "req-123"
}
```

#### 处理建议

1. **客户端处理**
   - 检查方法名拼写
   - 使用 Agent Card 验证能力
   - 动态适配可用方法

2. **服务端实现**
   - 返回可用方法列表
   - 提供拼写建议

#### 代码示例

```typescript
class A2AClient {
  private methodCache: Map<string, boolean> = new Map();
  private availableMethods: string[] = [];
  
  async initialize(): Promise<void> {
    // 从 Agent Card 获取支持的方法
    const card = await this.getAgentCard();
    this.availableMethods = card.capabilities.methods || [];
    
    // 预填充缓存
    this.availableMethods.forEach(m => this.methodCache.set(m, true));
  }
  
  async callMethod(method: string, params: unknown): Promise<unknown> {
    // 本地检查
    if (this.methodCache.size > 0 && !this.methodCache.has(method)) {
      const suggestion = this.findSimilarMethod(method);
      throw new A2AMethodNotFoundError(
        `Method "${method}" not supported`,
        suggestion
      );
    }
    
    const response = await this.sendRequest(method, params);
    
    if (response.error?.code === -32601) {
      // 更新本地缓存
      this.methodCache.set(method, false);
      
      const suggestion = response.error.data?.suggestion;
      throw new A2AMethodNotFoundError(
        response.error.message,
        suggestion,
        response.error.data?.available_methods
      );
    }
    
    return response.result;
  }
  
  private findSimilarMethod(method: string): string | null {
    // 简单的 Levenshtein 距离匹配
    const minDistance = 3;
    let bestMatch: string | null = null;
    let bestScore = Infinity;
    
    for (const available of this.availableMethods) {
      const distance = levenshteinDistance(method, available);
      if (distance < bestScore && distance <= minDistance) {
        bestScore = distance;
        bestMatch = available;
      }
    }
    
    return bestMatch;
  }
}

class A2AMethodNotFoundError extends Error {
  constructor(
    message: string,
    public suggestion?: string,
    public availableMethods?: string[]
  ) {
    super(message);
    this.name = 'A2AMethodNotFoundError';
  }
}
```

---

### 2.4 -32602 Invalid Params

#### 问题描述
方法参数无效。A2A 场景中常见：
- 缺少必填参数
- 参数类型不正确
- 参数值超出范围
- 参数组合不兼容

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "method": "tasks/send",
      "violations": [
        {
          "path": "task.contextId",
          "message": "Invalid contextId format",
          "expected": "UUID v4"
        },
        {
          "path": "message.parts[0].text",
          "message": "Text part cannot be empty"
        },
        {
          "path": "message.parts[1].file.bytes",
          "message": "Invalid base64 encoding"
        }
      ]
    }
  },
  "id": "req-123"
}
```

#### 处理建议

1. **参数验证**
   - 使用 JSON Schema 验证
   - 类型检查
   - 业务规则验证

2. **客户端处理**
   - 根据错误路径修正参数
   - 显示用户友好的错误信息

#### 代码示例

```typescript
// 使用 JSON Schema 验证
import Ajv from 'ajv';

const ajv = new Ajv({ allErrors: true });

// tasks/send 参数 schema
const taskSendSchema = {
  type: 'object',
  required: ['task', 'message'],
  properties: {
    task: {
      type: 'object',
      required: ['id'],
      properties: {
        id: { type: 'string', format: 'uuid' },
        contextId: { type: 'string', format: 'uuid' },
        status: {
          type: 'object',
          required: ['state'],
          properties: {
            state: {
              type: 'string',
              enum: ['submitted', 'working', 'input-required', 'completed', 'cancelled', 'failed']
            }
          }
        }
      }
    },
    message: {
      type: 'object',
      required: ['role', 'parts'],
      properties: {
        role: { type: 'string', enum: ['user', 'agent'] },
        parts: {
          type: 'array',
          minItems: 1,
          items: {
            type: 'object',
            required: ['type'],
            properties: {
              type: { type: 'string', enum: ['text', 'file', 'data'] }
            }
          }
        }
      }
    }
  }
};

function validateParams(method: string, params: unknown): void {
  const schema = getSchemaForMethod(method);
  if (!schema) return;
  
  const validate = ajv.compile(schema);
  const valid = validate(params);
  
  if (!valid && validate.errors) {
    const violations = validate.errors.map(err => ({
      path: err.instancePath || '/',
      message: err.message || 'Validation failed',
      params: err.params
    }));
    
    throw new A2AInvalidParamsError('Invalid parameters', violations);
  }
}

class A2AInvalidParamsError extends Error {
  constructor(
    message: string,
    public violations: Array<{
      path: string;
      message: string;
      params?: Record<string, unknown>;
    }>
  ) {
    super(message);
    this.name = 'A2AInvalidParamsError';
  }
}

// 使用示例
try {
  validateParams('tasks/send', params);
  await client.callMethod('tasks/send', params);
} catch (e) {
  if (e instanceof A2AInvalidParamsError) {
    for (const violation of e.violations) {
      console.error(`Parameter error at ${violation.path}: ${violation.message}`);
    }
  }
}
```

---

### 2.5 -32603 Internal Error

#### 问题描述
服务器内部错误，与 HTTP 500 类似，但在 JSON-RPC 层。常见原因：
- 未捕获的异常
- 资源不足
- 依赖服务失败

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "request_id": "req-abc123",
      "timestamp": "2024-03-30T14:56:00Z",
      "retry_possible": true
    }
  },
  "id": "req-123"
}
```

#### 处理建议

1. **重试逻辑**
   - 检查 `retry_possible` 标志
   - 使用指数退避

2. **错误追踪**
   - 保存 `request_id`
   - 联系服务提供方

#### 代码示例

```typescript
async function callWithInternalErrorHandling(
  client: A2AClient,
  method: string,
  params: unknown,
  maxRetries = 3
): Promise<unknown> {
  let lastRequestId: string | undefined;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await client.callMethod(method, params);
    } catch (e) {
      if (e instanceof A2AInternalError) {
        lastRequestId = e.requestId;
        
        if (e.retryPossible && attempt < maxRetries - 1) {
          console.warn(`Internal error (request: ${e.requestId}), retrying...`);
          await exponentialBackoff(attempt);
          continue;
        }
      }
      throw e;
    }
  }
  
  throw new A2AInternalError(
    `Internal error after ${maxRetries} attempts`,
    lastRequestId
  );
}

class A2AInternalError extends Error {
  constructor(
    message: string,
    public requestId?: string,
    public retryPossible: boolean = true
  ) {
    super(message);
    this.name = 'A2AInternalError';
  }
}
```

---

### 2.6 A2A 特定错误码 (-32001 到 -32010)

A2A 协议定义了特定于 Agent 交互的错误码。

#### 错误码列表

| 错误码 | 名称 | 描述 |
|--------|------|------|
| -32001 | TaskNotFound | 任务不存在 |
| -32002 | TaskCancelled | 任务已取消 |
| -32003 | TaskExpired | 任务已过期 |
| -32004 | InvalidContext | 上下文无效或已过期 |
| -32005 | MessageConflict | messageId 冲突 |
| -32006 | PartProcessingError | Part 处理失败 |
| -32007 | FileTooLarge | 文件超出大小限制 |
| -32008 | UnsupportedFormat | 不支持的文件格式 |
| -32009 | AgentUnavailable | Agent 不可用 |
| -32010 | CapabilityNotSupported | 能力不支持 |

---

#### -32001 TaskNotFound

##### 问题描述
指定的 taskId 不存在。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Task not found",
    "data": {
      "task_id": "task-abc123",
      "suggestion": "Create a new task using tasks/send"
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
async function getOrRetryTask(
  client: A2AClient,
  taskId: string
): Promise<Task> {
  try {
    return await client.callMethod('tasks/get', { id: taskId });
  } catch (e) {
    if (e instanceof A2ATaskNotFoundError) {
      console.warn(`Task ${taskId} not found, creating new task...`);
      return await client.callMethod('tasks/send', {
        task: { id: taskId },
        message: { role: 'user', parts: [] }
      });
    }
    throw e;
  }
}
```

---

#### -32002 TaskCancelled

##### 问题描述
任务已被取消，无法继续操作。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32002,
    "message": "Task cancelled",
    "data": {
      "task_id": "task-abc123",
      "cancelled_at": "2024-03-30T14:50:00Z",
      "reason": "User requested cancellation"
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
async function sendWithCancelledHandling(
  client: A2AClient,
  taskId: string,
  message: Message
): Promise<Task> {
  try {
    return await client.callMethod('tasks/send', {
      task: { id: taskId },
      message
    });
  } catch (e) {
    if (e instanceof A2ATaskCancelledError) {
      console.info(`Task ${taskId} was cancelled at ${e.cancelledAt}`);
      console.info(`Reason: ${e.reason}`);
      
      // 可以创建新任务
      const newTask = await client.callMethod('tasks/send', {
        message
      });
      console.info(`Created new task: ${newTask.id}`);
      return newTask;
    }
    throw e;
  }
}
```

---

#### -32003 TaskExpired

##### 问题描述
任务已过期，超过了有效期。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32003,
    "message": "Task expired",
    "data": {
      "task_id": "task-abc123",
      "expired_at": "2024-03-30T14:00:00Z",
      "ttl_hours": 24
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
class TaskManager {
  private taskCache: Map<string, { task: Task; createdAt: Date }> = new Map();
  
  async sendOrRefresh(taskId: string, message: Message): Promise<Task> {
    try {
      return await this.client.callMethod('tasks/send', {
        task: { id: taskId },
        message
      });
    } catch (e) {
      if (e instanceof A2ATaskExpiredError) {
        console.warn(`Task ${taskId} expired after ${e.ttlHours} hours`);
        
        // 清理缓存
        this.taskCache.delete(taskId);
        
        // 创建新任务
        return this.createTask(message);
      }
      throw e;
    }
  }
}
```

---

#### -32004 InvalidContext

##### 问题描述
contextId 无效或已过期。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32004,
    "message": "Invalid context",
    "data": {
      "context_id": "ctx-xyz789",
      "reason": "expired",
      "valid_contexts": ["ctx-abc123", "ctx-def456"]
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
class ContextManager {
  private activeContexts: Set<string> = new Set();
  
  async sendWithContext(
    client: A2AClient,
    message: Message,
    contextId?: string
  ): Promise<Task> {
    const taskId = generateTaskId();
    const requestContextId = contextId || this.getDefaultContext();
    
    try {
      return await client.callMethod('tasks/send', {
        task: { id: taskId, contextId: requestContextId },
        message
      });
    } catch (e) {
      if (e instanceof A2AInvalidContextError) {
        if (e.reason === 'expired') {
          // 移除过期上下文
          this.activeContexts.delete(requestContextId);
          
          // 使用新上下文重试
          return this.sendWithContext(client, message);
        }
        
        // 使用有效上下文重试
        if (e.validContexts && e.validContexts.length > 0) {
          return this.sendWithContext(client, message, e.validContexts[0]);
        }
      }
      throw e;
    }
  }
  
  private getDefaultContext(): string {
    // 创建新上下文
    return generateContextId();
  }
}
```

---

#### -32005 MessageConflict

##### 问题描述
messageId 与已存在的消息冲突，通常是因为重复发送。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32005,
    "message": "Message conflict",
    "data": {
      "message_id": "msg-123456",
      "existing_message_id": "msg-123456",
      "task_id": "task-abc123",
      "received_at": "2024-03-30T14:55:00Z"
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
class MessageDeduplicator {
  private sentMessages: Map<string, { message: Message; response: Task }> = new Map();
  
  async sendMessage(
    client: A2AClient,
    taskId: string,
    message: Message
  ): Promise<Task> {
    // 如果设置了 messageId，检查是否已发送
    if (message.messageId) {
      const cached = this.sentMessages.get(message.messageId);
      if (cached) {
        console.info(`Message ${message.messageId} already sent, returning cached response`);
        return cached.response;
      }
    }
    
    try {
      const response = await client.callMethod('tasks/send', {
        task: { id: taskId },
        message
      });
      
      // 缓存响应
      if (message.messageId) {
        this.sentMessages.set(message.messageId, { message, response });
      }
      
      return response;
    } catch (e) {
      if (e instanceof A2AMessageConflictError) {
        // 消息已存在，可能是之前的重试
        console.info(`Message ${message.messageId} conflict - already processed`);
        
        // 获取当前任务状态
        return await client.callMethod('tasks/get', { id: taskId });
      }
      throw e;
    }
  }
}
```

---

#### -32006 PartProcessingError

##### 问题描述
消息中的 Part 处理失败。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32006,
    "message": "Part processing error",
    "data": {
      "part_index": 1,
      "part_type": "file",
      "error": "Failed to decode base64 content",
      "recoverable": false
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
async function sendWithPartValidation(
  client: A2AClient,
  taskId: string,
  parts: Part[]
): Promise<Task> {
  // 预验证所有 parts
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    
    if (part.type === 'file' && part.file?.bytes) {
      try {
        // 验证 base64
        Buffer.from(part.file.bytes, 'base64');
      } catch {
        throw new A2AValidationError(
          `Part ${i}: Invalid base64 encoding`
        );
      }
    }
    
    if (part.type === 'text' && !part.text?.trim()) {
      throw new A2AValidationError(
        `Part ${i}: Text part cannot be empty`
      );
    }
  }
  
  try {
    return await client.callMethod('tasks/send', {
      task: { id: taskId },
      message: { role: 'user', parts }
    });
  } catch (e) {
    if (e instanceof A2APartProcessingError) {
      console.error(`Part ${e.partIndex} processing failed: ${e.error}`);
      
      if (e.recoverable) {
        // 尝试移除有问题的 part 后重试
        const validParts = parts.filter((_, i) => i !== e.partIndex);
        if (validParts.length > 0) {
          console.info('Retrying without problematic part...');
          return sendWithPartValidation(client, taskId, validParts);
        }
      }
    }
    throw e;
  }
}
```

---

#### -32007 FileTooLarge

##### 问题描述
文件大小超出限制。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32007,
    "message": "File too large",
    "data": {
      "file_name": "large-document.pdf",
      "file_size_mb": 150,
      "max_size_mb": 100,
      "suggestion": "Use file streaming or split the file"
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
const MAX_FILE_SIZE_MB = 100;

async function sendFilePart(
  client: A2AClient,
  taskId: string,
  filePath: string
): Promise<Task> {
  const stats = await fs.promises.stat(filePath);
  const sizeMB = stats.size / (1024 * 1024);
  
  if (sizeMB > MAX_FILE_SIZE_MB) {
    // 选项 1: 压缩文件
    const compressed = await compressFile(filePath);
    if (compressed.size / (1024 * 1024) <= MAX_FILE_SIZE_MB) {
      return sendFilePart(client, taskId, compressed.path);
    }
    
    // 选项 2: 使用文件引用而非嵌入
    const fileUrl = await uploadToStorage(filePath);
    return client.callMethod('tasks/send', {
      task: { id: taskId },
      message: {
        role: 'user',
        parts: [{
          type: 'file',
          file: {
            name: path.basename(filePath),
            url: fileUrl
          }
        }]
      }
    });
  }
  
  // 文件大小正常，嵌入 base64
  const content = await fs.promises.readFile(filePath);
  return client.callMethod('tasks/send', {
    task: { id: taskId },
    message: {
      role: 'user',
      parts: [{
        type: 'file',
        file: {
          name: path.basename(filePath),
          bytes: content.toString('base64'),
          mimeType: getMimeType(filePath)
        }
      }]
    }
  });
}
```

---

#### -32008 UnsupportedFormat

##### 问题描述
文件格式不支持。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32008,
    "message": "Unsupported format",
    "data": {
      "file_name": "document.xyz",
      "mime_type": "application/x-xyz",
      "supported_formats": [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "text/plain"
      ]
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
const SUPPORTED_MIME_TYPES = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/gif',
  'text/plain',
  'text/markdown'
]);

async function sendFileWithConversion(
  client: A2AClient,
  taskId: string,
  filePath: string
): Promise<Task> {
  const mimeType = getMimeType(filePath);
  
  if (!SUPPORTED_MIME_TYPES.has(mimeType)) {
    // 尝试转换格式
    const convertedPath = await convertToSupportedFormat(filePath, 'pdf');
    
    if (convertedPath) {
      console.info(`Converted ${path.basename(filePath)} to PDF`);
      return sendFilePart(client, taskId, convertedPath);
    }
    
    // 无法转换，作为原始数据处理
    console.warn(`Unsupported format ${mimeType}, sending as raw data`);
    return client.callMethod('tasks/send', {
      task: { id: taskId },
      message: {
        role: 'user',
        parts: [{
          type: 'data',
          data: {
            type: 'file-reference',
            value: filePath,
            mimeType
          }
        }]
      }
    });
  }
  
  return sendFilePart(client, taskId, filePath);
}
```

---

#### -32009 AgentUnavailable

##### 问题描述
目标 Agent 当前不可用。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32009,
    "message": "Agent unavailable",
    "data": {
      "agent_id": "agent-xyz789",
      "reason": "maintenance",
      "estimated_recovery": "2024-03-30T16:00:00Z",
      "fallback_agents": ["agent-abc123", "agent-def456"]
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
class AgentFailover {
  private agents: AgentInfo[];
  private currentIndex = 0;
  
  constructor(agents: AgentInfo[]) {
    this.agents = agents;
  }
  
  async request(method: string, params: unknown): Promise<unknown> {
    const maxAttempts = this.agents.length;
    const attemptedAgents: string[] = [];
    
    for (let i = 0; i < maxAttempts; i++) {
      const agent = this.agents[this.currentIndex];
      this.currentIndex = (this.currentIndex + 1) % this.agents.length;
      
      if (attemptedAgents.includes(agent.id)) continue;
      attemptedAgents.push(agent.id);
      
      try {
        return await this.callAgent(agent, method, params);
      } catch (e) {
        if (e instanceof A2AAgentUnavailableError) {
          console.warn(`Agent ${agent.id} unavailable: ${e.reason}`);
          
          // 使用建议的备用 Agent
          if (e.fallbackAgents && e.fallbackAgents.length > 0) {
            const fallback = this.findAgent(e.fallbackAgents[0]);
            if (fallback) {
              return await this.callAgent(fallback, method, params);
            }
          }
          
          continue;
        }
        throw e;
      }
    }
    
    throw new A2AError('All agents unavailable');
  }
  
  private findAgent(id: string): AgentInfo | undefined {
    return this.agents.find(a => a.id === id);
  }
}
```

---

#### -32010 CapabilityNotSupported

##### 问题描述
Agent 不支持请求的能力。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32010,
    "message": "Capability not supported",
    "data": {
      "requested_capability": "streaming",
      "supported_capabilities": ["text-generation", "image-analysis"],
      "agent_id": "agent-xyz789"
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
interface AgentCapability {
  id: string;
  name: string;
  version: string;
}

class CapabilityAwareClient {
  private agentCapabilities: Map<string, Set<string>> = new Map();
  
  async initialize(agentId: string): Promise<void> {
    const card = await this.getAgentCard(agentId);
    this.agentCapabilities.set(
      agentId,
      new Set(card.capabilities.map(c => c.id || c.name))
    );
  }
  
  hasCapability(agentId: string, capability: string): boolean {
    const caps = this.agentCapabilities.get(agentId);
    return caps?.has(capability) ?? false;
  }
  
  async requestWithCapability(
    agentId: string,
    capability: string,
    method: string,
    params: unknown
  ): Promise<unknown> {
    // 检查能力
    if (!this.hasCapability(agentId, capability)) {
      throw new A2ACapabilityError(
        `Agent ${agentId} does not support ${capability}`
      );
    }
    
    try {
      return await this.callMethod(agentId, method, params);
    } catch (e) {
      if (e instanceof A2ACapabilityNotSupportedError) {
        // 更新本地能力缓存
        const caps = this.agentCapabilities.get(agentId);
        caps?.delete(capability);
        
        throw new A2ACapabilityError(
          `Capability ${capability} no longer supported by ${agentId}`,
          e.supportedCapabilities
        );
      }
      throw e;
    }
  }
}
```

---

## 3. 业务层异常

业务层异常是 A2A 协议特有的，涉及 Task、Message、Part 等核心实体的状态问题。

### 3.1 Task 状态异常

#### cancelled 状态

##### 问题描述
任务被用户或系统取消，处于 `cancelled` 状态。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "task-abc123",
    "status": {
      "state": "cancelled",
      "timestamp": "2024-03-30T14:55:00Z"
    },
    "history": [
      {
        "role": "user",
        "parts": [{ "type": "text", "text": "Process this document" }]
      },
      {
        "role": "agent",
        "parts": [{ "type": "text", "text": "Starting processing..." }]
      }
    ]
  },
  "id": "req-123"
}
```

##### 处理建议

1. **检测取消状态**
   - 定期轮询 Task 状态
   - 在 `tasks/sendSubscribe` 中监听取消事件

2. **清理资源**
   - 取消相关操作
   - 释放锁定资源

##### 代码示例

```typescript
async function monitorTask(
  client: A2AClient,
  taskId: string,
  onStatusChange: (status: TaskStatus) => void
): Promise<Task> {
  // 使用 SSE 订阅状态变更
  const eventSource = new EventSource(
    `${client.baseUrl}/tasks/${taskId}/subscribe`
  );
  
  return new Promise((resolve, reject) => {
    eventSource.onmessage = (event) => {
      const task: Task = JSON.parse(event.data);
      
      onStatusChange(task.status);
      
      if (task.status.state === 'cancelled') {
        eventSource.close();
        reject(new A2ATaskCancelledError(
          'Task was cancelled',
          task.status.timestamp
        ));
        return;
      }
      
      if (task.status.state === 'completed') {
        eventSource.close();
        resolve(task);
        return;
      }
      
      if (task.status.state === 'failed') {
        eventSource.close();
        reject(new A2ATaskFailedError(
          task.status.message?.text || 'Task failed',
          task.status
        ));
        return;
      }
    };
    
    eventSource.onerror = (error) => {
      eventSource.close();
      reject(new A2AConnectionError('SSE connection failed'));
    };
  });
}
```

---

#### failed 状态

##### 问题描述
任务执行失败。

##### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "task-abc123",
    "status": {
      "state": "failed",
      "timestamp": "2024-03-30T14:56:00Z",
      "message": {
        "role": "agent",
        "parts": [{
          "type": "text",
          "text": "Failed to process document: Out of memory"
        }]
      }
    }
  },
  "id": "req-123"
}
```

##### 代码示例

```typescript
interface TaskFailure {
  taskId: string;
  timestamp: string;
  errorMessage: string;
  retryable: boolean;
}

async function handleFailedTask(
  client: A2AClient,
  task: Task
): Promise<Task | null> {
  if (task.status.state !== 'failed') {
    return null;
  }
  
  const failure: TaskFailure = {
    taskId: task.id,
    timestamp: task.status.timestamp,
    errorMessage: task.status.message?.parts
      ?.filter(p => p.type === 'text')
      .map(p => p.text)
      .join('\n') || 'Unknown error',
    retryable: isRetryableError(task.status.message)
  };
  
  console.error(`Task ${failure.taskId} failed: ${failure.errorMessage}`);
  
  if (failure.retryable) {
    console.info('Attempting to retry...');
    // 重新创建任务
    return client.callMethod('tasks/send', {
      message: task.history?.[0] || { role: 'user', parts: [] }
    });
  }
  
  return null;
}

function isRetryableError(message?: Message): boolean {
  const text = message?.parts
    ?.filter(p => p.type === 'text')
    .map(p => p.text)
    .join(' ') || '';
  
  const retryablePatterns = [
    /timeout/i,
    /temporary/i,
    /resource/i,
    /memory/i,
    /connection/i
  ];
  
  return retryablePatterns.some(p => p.test(text));
}
```

---

#### expired 状态

##### 问题描述
任务超过有效期。

##### 代码示例

```typescript
class TaskExpirationManager {
  private taskTTLs: Map<string, Date> = new Map();
  
  setTaskExpiration(taskId: string, ttlHours: number = 24): void {
    const expiration = new Date(Date.now() + ttlHours * 60 * 60 * 1000);
    this.taskTTLs.set(taskId, expiration);
  }
  
  isTaskExpired(taskId: string): boolean {
    const expiration = this.taskTTLs.get(taskId);
    if (!expiration) return false;
    return new Date() > expiration;
  }
  
  async getValidTask(
    client: A2AClient,
    taskId: string
  ): Promise<Task | null> {
    if (this.isTaskExpired(taskId)) {
      console.info(`Task ${taskId} has expired`);
      this.taskTTLs.delete(taskId);
      return null;
    }
    
    try {
      const task = await client.callMethod('tasks/get', { id: taskId });
      
      if (task.status.state === 'expired') {
        this.taskTTLs.delete(taskId);
        return null;
      }
      
      return task;
    } catch (e) {
      if (e instanceof A2ATaskExpiredError || e instanceof A2ATaskNotFoundError) {
        this.taskTTLs.delete(taskId);
        return null;
      }
      throw e;
    }
  }
}
```

---

### 3.2 contextId 无效或过期

#### 问题描述
上下文 ID 无效或已过期，无法关联到之前的对话或任务。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32004,
    "message": "Invalid context",
    "data": {
      "context_id": "ctx-old123",
      "reason": "expired",
      "expired_at": "2024-03-29T14:00:00Z",
      "suggestion": "Start a new conversation context"
    }
  },
  "id": "req-123"
}
```

#### 代码示例

```typescript
interface ConversationContext {
  id: string;
  createdAt: Date;
  lastActivity: Date;
  taskIds: string[];
}

class ContextManager {
  private contexts: Map<string, ConversationContext> = new Map();
  private contextTTLHours = 24;
  
  createContext(): ConversationContext {
    const context: ConversationContext = {
      id: generateContextId(),
      createdAt: new Date(),
      lastActivity: new Date(),
      taskIds: []
    };
    this.contexts.set(context.id, context);
    return context;
  }
  
  async getOrRefreshContext(contextId?: string): Promise<ConversationContext> {
    if (contextId) {
      const context = this.contexts.get(contextId);
      
      if (context && !this.isContextExpired(context)) {
        context.lastActivity = new Date();
        return context;
      }
      
      // Context 过期，移除
      if (context) {
        this.contexts.delete(contextId);
        console.info(`Context ${contextId} expired, creating new one`);
      }
    }
    
    return this.createContext();
  }
  
  private isContextExpired(context: ConversationContext): boolean {
    const hoursSinceActivity = 
      (Date.now() - context.lastActivity.getTime()) / (1000 * 60 * 60);
    return hoursSinceActivity > this.contextTTLHours;
  }
  
  async sendWithContext(
    client: A2AClient,
    contextId: string | undefined,
    message: Message
  ): Promise<{ task: Task; context: ConversationContext }> {
    const context = await this.getOrRefreshContext(contextId);
    
    try {
      const task = await client.callMethod('tasks/send', {
        task: { contextId: context.id },
        message
      });
      
      context.taskIds.push(task.id);
      context.lastActivity = new Date();
      
      return { task, context };
    } catch (e) {
      if (e instanceof A2AInvalidContextError) {
        // 服务器报告上下文无效，创建新的
        const newContext = this.createContext();
        
        const task = await client.callMethod('tasks/send', {
          task: { contextId: newContext.id },
          message
        });
        
        newContext.taskIds.push(task.id);
        
        return { task, context: newContext };
      }
      throw e;
    }
  }
}
```

---

### 3.3 messageId 冲突

#### 问题描述
发送的消息 ID 与已处理的消息重复。

#### 代码示例

```typescript
class IdempotentMessageSender {
  private pendingMessages: Map<string, {
    message: Message;
    taskId: string;
    sent: boolean;
    response?: Task;
  }> = new Map();
  
  async send(
    client: A2AClient,
    taskId: string,
    message: Message
  ): Promise<Task> {
    // 生成或使用现有的 messageId
    const messageId = message.messageId || generateMessageId();
    
    // 检查是否已处理
    const pending = this.pendingMessages.get(messageId);
    if (pending?.sent && pending.response) {
      return pending.response;
    }
    
    // 记录为处理中
    this.pendingMessages.set(messageId, {
      message: { ...message, messageId },
      taskId,
      sent: false
    });
    
    try {
      const response = await client.callMethod('tasks/send', {
        task: { id: taskId },
        message: { ...message, messageId }
      });
      
      // 标记为已发送
      this.pendingMessages.set(messageId, {
        message,
        taskId,
        sent: true,
        response
      });
      
      return response;
    } catch (e) {
      if (e instanceof A2AMessageConflictError) {
        // 消息已存在 - 这说明之前成功处理了
        console.info(`Message ${messageId} already processed`);
        
        // 获取当前任务状态作为响应
        const task = await client.callMethod('tasks/get', { id: taskId });
        
        this.pendingMessages.set(messageId, {
          message,
          taskId,
          sent: true,
          response: task
        });
        
        return task;
      }
      
      // 其他错误，移除记录
      this.pendingMessages.delete(messageId);
      throw e;
    }
  }
  
  // 清理旧记录
  cleanup(olderThanMs: number = 3600000): void {
    // 实现清理逻辑
  }
}
```

---

### 3.4 Part 解析失败

#### 问题描述
消息中的 Part 无法被正确解析。

#### 错误类型

1. **文本 Part 为空**
2. **文件 Part base64 无效**
3. **数据 Part JSON 无效**
4. **Part 类型不识别**

#### 代码示例

```typescript
interface PartValidationResult {
  valid: boolean;
  errors: Array<{
    path: string;
    message: string;
  }>;
}

function validatePart(part: Part, index: number): PartValidationResult {
  const errors: Array<{ path: string; message: string }> = [];
  
  switch (part.type) {
    case 'text':
      if (!part.text || part.text.trim().length === 0) {
        errors.push({
          path: `parts[${index}].text`,
          message: 'Text part cannot be empty'
        });
      }
      break;
      
    case 'file':
      if (part.file) {
        // 验证 base64
        if (part.file.bytes) {
          try {
            Buffer.from(part.file.bytes, 'base64');
          } catch {
            errors.push({
              path: `parts[${index}].file.bytes`,
              message: 'Invalid base64 encoding'
            });
          }
        }
        
        // 验证必需字段
        if (!part.file.name && !part.file.bytes && !part.file.url) {
          errors.push({
            path: `parts[${index}].file`,
            message: 'File part must have name, bytes, or url'
          });
        }
      } else {
        errors.push({
          path: `parts[${index}].file`,
          message: 'File part must have file property'
        });
      }
      break;
      
    case 'data':
      if (part.data) {
        if (!part.data.type) {
          errors.push({
            path: `parts[${index}].data.type`,
            message: 'Data part must have type'
          });
        }
        
        // 如果 data 是字符串，尝试解析为 JSON
        if (typeof part.data.value === 'string') {
          try {
            JSON.parse(part.data.value);
          } catch {
            errors.push({
              path: `parts[${index}].data.value`,
              message: 'Data value is not valid JSON'
            });
          }
        }
      } else {
        errors.push({
          path: `parts[${index}].data`,
          message: 'Data part must have data property'
        });
      }
      break;
      
    default:
      errors.push({
        path: `parts[${index}].type`,
        message: `Unknown part type: ${part.type}`
      });
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

function validateMessage(message: Message): PartValidationResult {
  const allErrors: Array<{ path: string; message: string }> = [];
  
  if (!message.parts || message.parts.length === 0) {
    return {
      valid: false,
      errors: [{ path: 'parts', message: 'Message must have at least one part' }]
    };
  }
  
  for (let i = 0; i < message.parts.length; i++) {
    const result = validatePart(message.parts[i], i);
    allErrors.push(...result.errors);
  }
  
  return {
    valid: allErrors.length === 0,
    errors: allErrors
  };
}
```

---

### 3.5 文件处理错误

#### 大小限制

##### 问题描述
文件超出大小限制。

##### 代码示例

```typescript
interface FileLimits {
  maxSizeBytes: number;
  maxTotalSizeBytes: number;
  supportedMimeTypes: Set<string>;
}

const DEFAULT_LIMITS: FileLimits = {
  maxSizeBytes: 100 * 1024 * 1024,  // 100 MB per file
  maxTotalSizeBytes: 500 * 1024 * 1024,  // 500 MB total
  supportedMimeTypes: new Set([
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/gif',
    'text/plain',
    'application/json'
  ])
};

class FileProcessor {
  constructor(private limits: FileLimits = DEFAULT_LIMITS) {}
  
  async processFile(filePath: string): Promise<FilePart> {
    const stats = await fs.promises.stat(filePath);
    
    // 检查大小
    if (stats.size > this.limits.maxSizeBytes) {
      throw new A2AFileTooLargeError(
        `File ${path.basename(filePath)} exceeds size limit`,
        stats.size,
        this.limits.maxSizeBytes
      );
    }
    
    // 检查 MIME 类型
    const mimeType = await this.detectMimeType(filePath);
    if (!this.limits.supportedMimeTypes.has(mimeType)) {
      throw new A2AUnsupportedFormatError(
        `Unsupported file format: ${mimeType}`,
        mimeType,
        Array.from(this.limits.supportedMimeTypes)
      );
    }
    
    // 读取并编码
    const content = await fs.promises.readFile(filePath);
    
    return {
      type: 'file',
      file: {
        name: path.basename(filePath),
        bytes: content.toString('base64'),
        mimeType
      }
    };
  }
  
  async processFiles(
    filePaths: string[]
  ): Promise<{ parts: FilePart[]; totalSize: number }> {
    const parts: FilePart[] = [];
    let totalSize = 0;
    
    for (const filePath of filePaths) {
      const stats = await fs.promises.stat(filePath);
      
      if (totalSize + stats.size > this.limits.maxTotalSizeBytes) {
        throw new A2AFileTooLargeError(
          'Total file size exceeds limit',
          totalSize + stats.size,
          this.limits.maxTotalSizeBytes
        );
      }
      
      const part = await this.processFile(filePath);
      parts.push(part);
      totalSize += stats.size;
    }
    
    return { parts, totalSize };
  }
}
```

---

#### 格式不支持

##### 代码示例

```typescript
interface ConversionResult {
  success: boolean;
  outputPath?: string;
  targetMimeType?: string;
  error?: string;
}

class FileConverter {
  private conversionMap: Map<string, string[]> = new Map([
    ['application/msword', ['application/pdf']],
    ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', ['application/pdf']],
    ['application/vnd.ms-excel', ['application/pdf', 'text/csv']],
    ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', ['application/pdf', 'text/csv']],
    ['application/vnd.ms-powerpoint', ['application/pdf']],
    ['application/vnd.openxmlformats-officedocument.presentationml.presentation', ['application/pdf']]
  ]);
  
  async convertToSupported(
    filePath: string,
    supportedTypes: Set<string>
  ): Promise<ConversionResult> {
    const mimeType = await this.detectMimeType(filePath);
    
    if (supportedTypes.has(mimeType)) {
      return { success: true, outputPath: filePath, targetMimeType: mimeType };
    }
    
    const targetTypes = this.conversionMap.get(mimeType);
    if (!targetTypes) {
      return {
        success: false,
        error: `No conversion available for ${mimeType}`
      };
    }
    
    // 找到支持的转换目标
    const targetType = targetTypes.find(t => supportedTypes.has(t));
    if (!targetType) {
      return {
        success: false,
        error: `None of the conversion targets are supported`
      };
    }
    
    // 执行转换
    const outputPath = await this.convert(filePath, targetType);
    
    return {
      success: true,
      outputPath,
      targetMimeType: targetType
    };
  }
  
  private async convert(
    inputPath: string,
    targetMimeType: string
  ): Promise<string> {
    // 实现实际的转换逻辑
    // 可以使用外部工具如 LibreOffice, ImageMagick 等
    const outputPath = inputPath.replace(/\.[^.]+$/, this.getExtension(targetMimeType));
    
    // 示例: 使用 LibreOffice 转换
    await execFile('libreoffice', [
      '--headless',
      '--convert-to',
      this.getExtension(targetMimeType),
      '--outdir',
      path.dirname(outputPath),
      inputPath
    ]);
    
    return outputPath;
  }
  
  private getExtension(mimeType: string): string {
    const map: Record<string, string> = {
      'application/pdf': 'pdf',
      'text/csv': 'csv',
      'image/png': 'png',
      'image/jpeg': 'jpg'
    };
    return map[mimeType] || 'bin';
  }
}
```

---

## 4. 边界情况

边界情况是那些不常见但需要正确处理的场景。

### 4.1 空 parts 数组

#### 问题描述
Message 的 parts 数组为空。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "path": "message.parts",
      "message": "Parts array cannot be empty",
      "minimum_length": 1
    }
  },
  "id": "req-123"
}
```

#### 处理建议

1. **客户端验证**
   - 发送前检查 parts 非空
   - 如果没有内容，不发送消息

2. **服务端处理**
   - 拒绝空 parts
   - 返回清晰的错误信息

#### 代码示例

```typescript
function createMessage(parts: Part[]): Message {
  if (!parts || parts.length === 0) {
    throw new A2AValidationError('Message must have at least one part');
  }
  
  return {
    role: 'user',
    parts
  };
}

// 处理可能为空的内容
async function sendUserInput(
  client: A2AClient,
  taskId: string,
  userInput: string | null
): Promise<Task | null> {
  if (!userInput?.trim()) {
    console.warn('Empty user input, skipping message');
    return null;
  }
  
  const message: Message = {
    role: 'user',
    parts: [{ type: 'text', text: userInput }]
  };
  
  return client.callMethod('tasks/send', {
    task: { id: taskId },
    message
  });
}
```

---

### 4.2 超大消息体

#### 问题描述
消息体超出大小限制。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "path": "message",
      "message": "Message size exceeds limit",
      "size_bytes": 52428800,
      "max_size_bytes": 10485760
    }
  },
  "id": "req-123"
}
```

#### 处理建议

1. **分块处理**
   - 将大文件分块上传
   - 使用流式传输

2. **压缩**
   - 压缩大文件
   - 使用 gzip 压缩请求体

#### 代码示例

```typescript
interface ChunkUploadResult {
  uploadId: string;
  chunks: number;
  completeUrl?: string;
}

class ChunkedUploader {
  private chunkSize = 5 * 1024 * 1024; // 5 MB per chunk
  
  async uploadLargeFile(
    client: A2AClient,
    taskId: string,
    filePath: string
  ): Promise<Task> {
    const stats = await fs.promises.stat(filePath);
    const totalChunks = Math.ceil(stats.size / this.chunkSize);
    
    if (totalChunks <= 1) {
      // 文件足够小，直接上传
      return this.uploadFile(client, taskId, filePath);
    }
    
    // 初始化分块上传
    const uploadId = generateUploadId();
    console.info(`Starting chunked upload: ${totalChunks} chunks`);
    
    // 上传各分块
    for (let i = 0; i < totalChunks; i++) {
      const chunk = await this.readChunk(filePath, i);
      const chunkPart: Part = {
        type: 'data',
        data: {
          type: 'file-chunk',
          value: JSON.stringify({
            uploadId,
            chunkIndex: i,
            totalChunks,
            fileName: path.basename(filePath),
            data: chunk.toString('base64')
          })
        }
      };
      
      await client.callMethod('tasks/send', {
        task: { id: taskId },
        message: {
          role: 'user',
          parts: [chunkPart]
        }
      });
      
      console.info(`Uploaded chunk ${i + 1}/${totalChunks}`);
    }
    
    // 发送完成信号
    return client.callMethod('tasks/send', {
      task: { id: taskId },
      message: {
        role: 'user',
        parts: [{
          type: 'data',
          data: {
            type: 'file-chunk-complete',
            value: JSON.stringify({
              uploadId,
              fileName: path.basename(filePath),
              totalChunks
            })
          }
        }]
      }
    });
  }
  
  private async readChunk(filePath: string, index: number): Promise<Buffer> {
    const fd = await fs.promises.open(filePath, 'r');
    const buffer = Buffer.alloc(this.chunkSize);
    
    await fd.read(buffer, 0, this.chunkSize, index * this.chunkSize);
    await fd.close();
    
    return buffer;
  }
  
  private async uploadFile(
    client: A2AClient,
    taskId: string,
    filePath: string
  ): Promise<Task> {
    const content = await fs.promises.readFile(filePath);
    
    return client.callMethod('tasks/send', {
      task: { id: taskId },
      message: {
        role: 'user',
        parts: [{
          type: 'file',
          file: {
            name: path.basename(filePath),
            bytes: content.toString('base64')
          }
        }]
      }
    });
  }
}
```

---

### 4.3 无效的 base64

#### 问题描述
文件 Part 中的 base64 编码无效。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32006,
    "message": "Part processing error",
    "data": {
      "part_index": 2,
      "error": "Invalid base64: unexpected character at position 1024",
      "expected_format": "RFC 4648 base64"
    }
  },
  "id": "req-123"
}
```

#### 代码示例

```typescript
function validateBase64(input: string): { valid: boolean; error?: string } {
  // 基本格式检查
  const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
  
  if (!base64Regex.test(input)) {
    // 找到无效字符
    const invalidChars = input.split('').findIndex(
      c => !/[A-Za-z0-9+/=]/.test(c)
    );
    return {
      valid: false,
      error: `Invalid character at position ${invalidChars}`
    };
  }
  
  // 长度检查（必须是 4 的倍数）
  if (input.length % 4 !== 0) {
    return {
      valid: false,
      error: `Invalid length: ${input.length} is not a multiple of 4`
    };
  }
  
  // 尝试解码
  try {
    Buffer.from(input, 'base64');
    return { valid: true };
  } catch (e) {
    return {
      valid: false,
      error: (e as Error).message
    };
  }
}

// 安全编码
function safeBase64Encode(data: Buffer | string): string {
  if (Buffer.isBuffer(data)) {
    return data.toString('base64');
  }
  return Buffer.from(data, 'utf-8').toString('base64');
}

// 安全解码
function safeBase64Decode(base64: string): Buffer {
  // 移除可能的空白和数据 URL 前缀
  const cleaned = base64
    .replace(/\s/g, '')
    .replace(/^data:[^;]+;base64,/, '');
  
  if (!validateBase64(cleaned).valid) {
    throw new A2AValidationError('Invalid base64 encoding');
  }
  
  return Buffer.from(cleaned, 'base64');
}
```

---

### 4.4 无效的 JSON

#### 问题描述
请求体不是有效的 JSON。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32700,
    "message": "Parse error",
    "data": {
      "position": 256,
      "line": 10,
      "column": 15,
      "context": "...\"text\": \"hello world\n\"...",
      "expected": "string escape or end of string"
    }
  },
  "id": null
}
```

#### 代码示例

```typescript
function safeJsonParse<T>(text: string): T {
  try {
    return JSON.parse(text);
  } catch (e) {
    const error = e as SyntaxError;
    
    // 尝试提取错误位置
    const positionMatch = error.message.match(/position (\d+)/);
    const position = positionMatch ? parseInt(positionMatch[1]) : -1;
    
    if (position >= 0) {
      // 计算行号和列号
      const { line, column, context } = getErrorContext(text, position);
      
      throw new A2AJsonParseError(
        `JSON parse error at line ${line}, column ${column}`,
        {
          position,
          line,
          column,
          context,
          message: error.message
        }
      );
    }
    
    throw new A2AJsonParseError(error.message);
  }
}

function getErrorContext(
  text: string,
  position: number
): { line: number; column: number; context: string } {
  const lines = text.substring(0, position).split('\n');
  const line = lines.length;
  const column = lines[lines.length - 1].length + 1;
  
  // 提取错误上下文
  const start = Math.max(0, position - 20);
  const end = Math.min(text.length, position + 20);
  const context = text.substring(start, end);
  
  return { line, column, context };
}

class A2AJsonParseError extends Error {
  constructor(
    message: string,
    public details?: {
      position: number;
      line: number;
      column: number;
      context: string;
      message: string;
    }
  ) {
    super(message);
    this.name = 'A2AJsonParseError';
  }
}
```

---

### 4.5 缺失必填字段

#### 问题描述
请求缺少必填字段。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {
      "missing_fields": [
        {
          "path": "task.id",
          "type": "string",
          "required": true
        },
        {
          "path": "message.role",
          "type": "string",
          "required": true,
          "allowed_values": ["user", "agent"]
        }
      ]
    }
  },
  "id": null
}
```

#### 代码示例

```typescript
interface FieldSpec {
  path: string;
  type: string;
  required: boolean;
  allowedValues?: unknown[];
  defaultValue?: unknown;
}

const TASK_SEND_FIELDS: FieldSpec[] = [
  { path: 'task.id', type: 'string', required: true },
  { path: 'task.contextId', type: 'string', required: false },
  { path: 'message', type: 'object', required: true },
  { path: 'message.role', type: 'string', required: true, allowedValues: ['user', 'agent'] },
  { path: 'message.parts', type: 'array', required: true },
  { path: 'message.messageId', type: 'string', required: false }
];

function validateFields(
  params: Record<string, unknown>,
  specs: FieldSpec[]
): { valid: boolean; missing: FieldSpec[]; defaults: Record<string, unknown> } {
  const missing: FieldSpec[] = [];
  const defaults: Record<string, unknown> = {};
  
  for (const spec of specs) {
    const value = getNestedValue(params, spec.path);
    
    if (value === undefined) {
      if (spec.required) {
        missing.push(spec);
      } else if (spec.defaultValue !== undefined) {
        setNestedValue(defaults, spec.path, spec.defaultValue);
      }
    } else if (spec.allowedValues && !spec.allowedValues.includes(value)) {
      // 值不在允许范围内
      missing.push({
        ...spec,
        type: `${spec.type} (one of: ${spec.allowedValues.join(', ')})`
      });
    }
  }
  
  return {
    valid: missing.length === 0,
    missing,
    defaults
  };
}

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce((current, key) => {
    return current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined;
  }, obj as unknown);
}

function setNestedValue(
  obj: Record<string, unknown>,
  path: string,
  value: unknown
): void {
  const keys = path.split('.');
  const lastKey = keys.pop()!;
  
  const target = keys.reduce((current, key) => {
    if (!(current as Record<string, unknown>)[key]) {
      (current as Record<string, unknown>)[key] = {};
    }
    return (current as Record<string, unknown>)[key];
  }, obj);
  
  target[lastKey] = value;
}

// 使用示例
function prepareTaskSendParams(
  params: Partial<TaskSendParams>
): TaskSendParams {
  const result = validateFields(params as Record<string, unknown>, TASK_SEND_FIELDS);
  
  if (!result.valid) {
    const missingPaths = result.missing.map(f => f.path).join(', ');
    throw new A2AValidationError(`Missing required fields: ${missingPaths}`);
  }
  
  return {
    ...result.defaults,
    ...params
  } as TaskSendParams;
}
```

---

### 4.6 类型不匹配

#### 问题描述
字段值的类型与预期不符。

#### 错误响应示例

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "type_errors": [
        {
          "path": "task.id",
          "expected": "string",
          "received": "number",
          "received_value": 12345
        },
        {
          "path": "message.parts",
          "expected": "array",
          "received": "object"
        }
      ]
    }
  },
  "id": "req-123"
}
```

#### 代码示例

```typescript
interface TypeSpec {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array' | 'null';
  optional?: boolean;
  items?: TypeSpec;
  properties?: Record<string, TypeSpec>;
}

function validateType(value: unknown, spec: TypeSpec, path: string = ''): string[] {
  const errors: string[] = [];
  
  // 检查可选
  if (value === undefined || value === null) {
    if (!spec.optional) {
      errors.push(`${path}: required field is ${value === undefined ? 'missing' : 'null'}`);
    }
    return errors;
  }
  
  // 检查类型
  const actualType = Array.isArray(value) ? 'array' : typeof value;
  
  if (spec.type === 'array') {
    if (!Array.isArray(value)) {
      errors.push(`${path}: expected array, got ${actualType}`);
      return errors;
    }
    
    if (spec.items) {
      for (let i = 0; i < value.length; i++) {
        errors.push(...validateType(value[i], spec.items, `${path}[${i}]`));
      }
    }
  } else if (spec.type === 'object') {
    if (typeof value !== 'object' || Array.isArray(value)) {
      errors.push(`${path}: expected object, got ${actualType}`);
      return errors;
    }
    
    if (spec.properties) {
      for (const [key, propSpec] of Object.entries(spec.properties)) {
        errors.push(...validateType(
          (value as Record<string, unknown>)[key],
          propSpec,
          `${path}.${key}`
        ));
      }
    }
  } else if (actualType !== spec.type) {
    errors.push(`${path}: expected ${spec.type}, got ${actualType}`);
  }
  
  return errors;
}

// Part 类型验证
const PART_TYPE_SPEC: TypeSpec = {
  type: 'object',
  properties: {
    type: { type: 'string' },
    text: { type: 'string', optional: true },
    file: { type: 'object', optional: true },
    data: { type: 'object', optional: true }
  }
};

const MESSAGE_TYPE_SPEC: TypeSpec = {
  type: 'object',
  properties: {
    role: { type: 'string' },
    parts: {
      type: 'array',
      items: PART_TYPE_SPEC
    },
    messageId: { type: 'string', optional: true }
  }
};

function validateMessageTypes(message: unknown): { valid: boolean; errors: string[] } {
  const errors = validateType(message, MESSAGE_TYPE_SPEC, 'message');
  return {
    valid: errors.length === 0,
    errors
  };
}

// 自动类型转换
function coerceTypes(
  value: unknown,
  expectedType: string
): unknown {
  if (expectedType === 'string' && typeof value === 'number') {
    return String(value);
  }
  
  if (expectedType === 'number' && typeof value === 'string') {
    const num = Number(value);
    if (!isNaN(num)) {
      return num;
    }
  }
  
  if (expectedType === 'boolean' && typeof value === 'string') {
    if (value === 'true') return true;
    if (value === 'false') return false;
  }
  
  return value;
}
```

---

## 5. 通用错误处理模式

### 5.1 错误分类与处理策略

```typescript
// 错误基类
class A2AError extends Error {
  constructor(
    message: string,
    public code?: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'A2AError';
  }
}

// 具体错误类型
class A2ANetworkError extends A2AError {
  constructor(message: string, public isRetryable: boolean = true) {
    super(message);
    this.name = 'A2ANetworkError';
  }
}

class A2ATimeoutError extends A2AError {
  constructor(message: string, public type: 'connect' | 'read' | 'write') {
    super(message);
    this.name = 'A2ATimeoutError';
  }
}

class A2AAuthError extends A2AError {
  constructor(message: string, public isTokenExpired: boolean = false) {
    super(message, 401);
    this.name = 'A2AAuthError';
  }
}

class A2AValidationError extends A2AError {
  constructor(
    message: string,
    public violations: Array<{ path: string; message: string }> = []
  ) {
    super(message, -32602);
    this.name = 'A2AValidationError';
  }
}

// 错误处理器
class A2AErrorHandler {
  private retryableCodes = new Set([
    408, 429, 500, 502, 503, 504,
    -32603, // Internal error
    -32009  // Agent unavailable
  ]);
  
  classify(error: unknown): {
    type: string;
    retryable: boolean;
    userMessage: string;
  } {
    if (error instanceof A2ANetworkError) {
      return {
        type: 'network',
        retryable: error.isRetryable,
        userMessage: '网络连接问题，请检查网络后重试'
      };
    }
    
    if (error instanceof A2ATimeoutError) {
      return {
        type: 'timeout',
        retryable: error.type !== 'connect',
        userMessage: error.type === 'connect' 
          ? '无法连接到服务器'
          : '服务器响应超时，任务可能仍在处理'
      };
    }
    
    if (error instanceof A2AAuthError) {
      return {
        type: 'auth',
        retryable: error.isTokenExpired,
        userMessage: error.isTokenExpired
          ? '登录已过期，请重新登录'
          : '认证失败，请检查凭证'
      };
    }
    
    if (error instanceof A2AValidationError) {
      return {
        type: 'validation',
        retryable: false,
        userMessage: `参数错误: ${error.violations.map(v => v.message).join(', ')}`
      };
    }
    
    if (error instanceof A2AError && error.code) {
      return {
        type: 'protocol',
        retryable: this.retryableCodes.has(error.code),
        userMessage: this.getUserMessageForCode(error.code)
      };
    }
    
    return {
      type: 'unknown',
      retryable: false,
      userMessage: '发生未知错误'
    };
  }
  
  private getUserMessageForCode(code: number): string {
    const messages: Record<number, string> = {
      400: '请求格式不正确',
      401: '未授权访问',
      403: '没有权限执行此操作',
      404: '请求的资源不存在',
      429: '请求过于频繁，请稍后重试',
      500: '服务器内部错误',
      502: '网关错误',
      503: '服务暂时不可用',
      [-32700]: '请求解析失败',
      [-32600]: '无效的请求',
      [-32601]: '方法不存在',
      [-32602]: '参数无效',
      [-32603]: '服务器内部错误',
      [-32001]: '任务不存在',
      [-32002]: '任务已取消',
      [-32003]: '任务已过期',
      [-32004]: '上下文无效',
      [-32005]: '消息冲突',
      [-32006]: '消息处理失败',
      [-32007]: '文件过大',
      [-32008]: '不支持的文件格式',
      [-32009]: 'Agent 不可用',
      [-32010]: '能力不支持'
    };
    
    return messages[code] || `错误码: ${code}`;
  }
}
```

---

### 5.2 统一错误处理中间件

```typescript
interface ErrorContext {
  method: string;
  params: unknown;
  attempt: number;
  timestamp: Date;
}

class ErrorHandlingMiddleware {
  private errorHandler = new A2AErrorHandler();
  private maxRetries = 3;
  
  async execute<T>(
    operation: () => Promise<T>,
    context: ErrorContext
  ): Promise<T> {
    let lastError: unknown;
    
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        const classified = this.errorHandler.classify(error);
        
        // 记录错误
        this.logError(error, classified, context, attempt);
        
        // 检查是否可重试
        if (!classified.retryable || attempt === this.maxRetries - 1) {
          break;
        }
        
        // 等待后重试
        await this.waitForRetry(attempt, error);
      }
    }
    
    throw lastError;
  }
  
  private logError(
    error: unknown,
    classified: { type: string; retryable: boolean; userMessage: string },
    context: ErrorContext,
    attempt: number
  ): void {
    console.error({
      timestamp: context.timestamp.toISOString(),
      method: context.method,
      attempt,
      errorType: classified.type,
      retryable: classified.retryable,
      message: error instanceof Error ? error.message : String(error),
      code: error instanceof A2AError ? error.code : undefined
    });
  }
  
  private async waitForRetry(attempt: number, error: unknown): Promise<void> {
    let delay = 1000 * Math.pow(2, attempt);
    
    // 处理 Rate Limit
    if (error instanceof A2AError && error.code === 429 && error.data) {
      const retryAfter = (error.data as { retry_after?: number }).retry_after;
      if (retryAfter) {
        delay = retryAfter * 1000;
      }
    }
    
    // 添加抖动
    delay += Math.random() * 1000;
    
    await new Promise(resolve => setTimeout(resolve, delay));
  }
}
```

---

### 5.3 客户端错误处理最佳实践

```typescript
class RobustA2AClient {
  private middleware = new ErrorHandlingMiddleware();
  
  async callMethod<T>(
    method: string,
    params: unknown
  ): Promise<T> {
    return this.middleware.execute(
      () => this.doCall<T>(method, params),
      {
        method,
        params,
        attempt: 0,
        timestamp: new Date()
      }
    );
  }
  
  private async doCall<T>(method: string, params: unknown): Promise<T> {
    const response = await fetch(this.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method,
        params,
        id: generateRequestId()
      })
    });
    
    // 处理 HTTP 错误
    if (!response.ok) {
      await this.handleHttpError(response);
    }
    
    // 解析响应
    const data = await response.json();
    
    // 处理 JSON-RPC 错误
    if (data.error) {
      throw new A2AError(
        data.error.message,
        data.error.code,
        data.error.data
      );
    }
    
    return data.result;
  }
  
  private async handleHttpError(response: Response): Promise<never> {
    const body = await response.text();
    let data: unknown;
    
    try {
      data = JSON.parse(body);
    } catch {
      data = { message: body };
    }
    
    throw new A2AError(
      (data as { message?: string }).message || `HTTP ${response.status}`,
      response.status,
      data
    );
  }
}

// 使用示例
async function main() {
  const client = new RobustA2AClient('https://agent.example.com/rpc', 'token');
  
  try {
    const task = await client.callMethod<Task>('tasks/send', {
      task: { id: 'task-123' },
      message: {
        role: 'user',
        parts: [{ type: 'text', text: 'Hello!' }]
      }
    });
    
    console.log('Task created:', task.id);
  } catch (error) {
    const handler = new A2AErrorHandler();
    const classified = handler.classify(error);
    
    console.error('Error:', classified.userMessage);
    
    if (classified.retryable) {
      console.log('This error is retryable');
    }
  }
}
```

---

## 总结

A2A 异常处理需要关注三个层次：

1. **HTTP 层**：网络、认证、服务器状态
2. **JSON-RPC 层**：协议规范、方法调用
3. **业务层**：Task、Message、Part 等实体状态

关键实践：

- ✅ 始终验证输入参数
- ✅ 实现指数退避重试
- ✅ 处理超时时考虑任务可能仍在进行
- ✅ 使用 messageId 实现幂等性
- ✅ 区分可重试和不可重试的错误
- ✅ 记录详细的错误日志
- ✅ 为用户提供友好的错误信息
