# A2A 错误码参考手册

> 完整的错误码列表、响应格式和处理示例

---

## 目录

1. [HTTP 层错误详解](#1-http-层错误详解)
2. [JSON-RPC 层错误详解](#2-json-rpc-层错误详解)
3. [业务层错误详解](#3-业务层错误详解)
4. [边缘情况处理](#4-边缘情况处理)
5. [完整代码示例](#5-完整代码示例)

---

## 1. HTTP 层错误详解

### 1.1 400 Bad Request

**原因**：
- Content-Type 头缺失或错误
- 请求体为空
- HTTP 方法不支持

**响应示例**：

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

**处理代码**：

```typescript
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
```

---

### 1.2 401 Unauthorized

**原因**：
- Token 缺失
- Token 过期
- Token 格式错误

**响应示例**：

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

**处理代码**：

```typescript
class A2AClient {
  private token: string;
  private refreshToken: string;
  
  async request(method: string, params: unknown) {
    const response = await this.sendRequest(method, params);
    
    if (response.status === 401) {
      const error = await response.json();
      
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

**原因**：
- 访问其他 Agent 的私有资源
- 执行超出权限范围的操作
- IP 被限制

**响应示例**：

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

**处理代码**：

```typescript
async function handleForbidden(response: Response) {
  const error = await response.json();
  
  switch (error.details?.reason) {
    case 'agent_not_authorized':
      throw new A2APermissionError(
        `Missing permission: ${error.details.required_permission}`
      );
      
    case 'resource_not_shared':
      throw new A2AResourceError('Resource not accessible in current context');
      
    default:
      throw new A2AForbiddenError(error.message);
  }
}
```

---

### 1.4 404 Not Found

**原因**：
- Task 不存在
- Agent 端点未注册
- Message 不存在

**响应示例**：

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

**处理代码**：

```typescript
async function getTask(taskId: string): Promise<Task> {
  const response = await fetch(`/tasks/${taskId}`);
  
  if (response.status === 404) {
    console.warn(`Task ${taskId} not found, creating new one...`);
    return createNewTask();
  }
  
  return response.json();
}

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

**原因**：
- 每秒请求数 (RPS) 超限
- 每分钟请求数超限
- 并发连接数超限

**响应示例**：

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

**处理代码**：

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
          
          this.remaining = parseInt(
            response.headers.get('X-RateLimit-Remaining') || '100'
          );
          
          if (response.status === 429) {
            const retryAfter = parseInt(
              response.headers.get('Retry-After') || '60'
            );
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
        await sleep(1000);
      }
      
      const task = this.queue.shift();
      await task!();
    }
    
    this.isProcessing = false;
  }
}
```

---

### 1.6 500/502/503 服务端错误

**500 Internal Server Error**：服务器内部未捕获异常

**502 Bad Gateway**：网关从上游收到无效响应

**503 Service Unavailable**：服务维护或过载

**处理策略**：
- 实现指数退避重试
- 记录 request_id 用于追踪
- 503 使用 Retry-After 头

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
      
      if (response.status >= 500 && response.status < 600) {
        const error = await response.json();
        const requestId = error.request_id;
        console.error(`Server error (request_id: ${requestId}), attempt ${attempt + 1}`);
        
        if (attempt < maxRetries - 1) {
          const delay = 1000 * Math.pow(2, attempt) + Math.random() * 1000;
          await sleep(delay);
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
```

---

### 1.7 超时处理

**超时类型**：
- 连接超时：网络问题
- 读取超时：处理缓慢
- Agent 响应超时：长任务

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
    
    const readTimer = setTimeout(() => {
      controller.abort(new DOMException('Read timeout', 'TimeoutError'));
    }, readTimeout);
    
    return response;
    
  } catch (e) {
    if (e instanceof DOMException && e.name === 'TimeoutError') {
      throw new A2ATimeoutError(
        e.message,
        e.message === 'Connection timeout' ? 'connect' : 'read'
      );
    }
    throw e;
  }
}
```

---

## 2. JSON-RPC 层错误详解

### 2.1 -32700 Parse Error

**原因**：
- JSON 语法错误
- 编码问题
- 请求体被截断

**响应示例**：

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

**处理代码**：

```typescript
function safeStringify(data: unknown): string {
  try {
    const json = JSON.stringify(data);
    JSON.parse(json); // 验证可解析
    return json;
  } catch (e) {
    throw new A2AParseError(`Invalid JSON: ${(e as Error).message}`);
  }
}
```

---

### 2.2 -32600 Invalid Request

**原因**：
- 缺少必填字段（jsonrpc, method）
- jsonrpc 版本不是 "2.0"
- id 类型不正确

**响应示例**：

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {
      "violations": [
        { "field": "jsonrpc", "expected": "2.0", "received": "1.0" },
        { "field": "params", "expected": "object or array", "received": "string" }
      ]
    }
  },
  "id": null
}
```

**处理代码**：

```typescript
function validateRequest(request: unknown): JsonRpcRequest {
  if (typeof request !== 'object' || request === null) {
    throw new A2AInvalidRequestError('Request must be an object');
  }
  
  const req = request as Record<string, unknown>;
  const violations: Array<{ field: string; message: string }> = [];
  
  if (req.jsonrpc !== '2.0') {
    violations.push({
      field: 'jsonrpc',
      message: `Expected "2.0", received ${JSON.stringify(req.jsonrpc)}`
    });
  }
  
  if (typeof req.method !== 'string' || req.method.length === 0) {
    violations.push({
      field: 'method',
      message: 'Method must be a non-empty string'
    });
  }
  
  if (violations.length > 0) {
    throw new A2AInvalidRequestError('Invalid request structure', violations);
  }
  
  return req as JsonRpcRequest;
}
```

---

### 2.3 -32601 Method Not Found

**原因**：
- 方法名拼写错误
- Agent 不支持该能力
- 版本不匹配

**响应示例**：

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": {
      "method": "tasks/sendMesage",
      "suggestion": "Did you mean tasks/sendMessage?",
      "available_methods": ["tasks/send", "tasks/get", "tasks/cancel"]
    }
  },
  "id": "req-123"
}
```

**处理代码**：

```typescript
class A2AClient {
  private methodCache: Map<string, boolean> = new Map();
  
  async callMethod(method: string, params: unknown): Promise<unknown> {
    if (this.methodCache.size > 0 && !this.methodCache.has(method)) {
      throw new A2AMethodNotFoundError(`Method "${method}" not supported`);
    }
    
    const response = await this.sendRequest(method, params);
    
    if (response.error?.code === -32601) {
      this.methodCache.set(method, false);
      throw new A2AMethodNotFoundError(
        response.error.message,
        response.error.data?.suggestion
      );
    }
    
    return response.result;
  }
}
```

---

### 2.4 -32602 Invalid Params

**原因**：
- 缺少必填参数
- 参数类型不正确
- 参数值超出范围

**响应示例**：

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "violations": [
        { "path": "task.contextId", "message": "Invalid contextId format" },
        { "path": "message.parts[0].text", "message": "Text part cannot be empty" }
      ]
    }
  },
  "id": "req-123"
}
```

**使用 JSON Schema 验证**：

```typescript
import Ajv from 'ajv';

const ajv = new Ajv({ allErrors: true });

const taskSendSchema = {
  type: 'object',
  required: ['task', 'message'],
  properties: {
    task: {
      type: 'object',
      required: ['id'],
      properties: {
        id: { type: 'string', format: 'uuid' },
        contextId: { type: 'string', format: 'uuid' }
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
            required: ['type']
          }
        }
      }
    }
  }
};

function validateParams(method: string, params: unknown): void {
  const validate = ajv.compile(taskSendSchema);
  if (!validate(params)) {
    throw new A2AInvalidParamsError('Invalid parameters', validate.errors);
  }
}
```

---

### 2.5 -32603 Internal Error

**原因**：
- 未捕获的异常
- 资源不足
- 依赖服务失败

**响应示例**：

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Internal error",
    "data": {
      "request_id": "req-abc123",
      "retry_possible": true
    }
  },
  "id": "req-123"
}
```

**处理代码**：

```typescript
async function callWithRetry(
  client: A2AClient,
  method: string,
  params: unknown,
  maxRetries = 3
): Promise<unknown> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await client.callMethod(method, params);
    } catch (e) {
      if (e instanceof A2AInternalError && e.retryPossible) {
        console.warn(`Internal error, retrying... (${attempt + 1}/${maxRetries})`);
        await exponentialBackoff(attempt);
        continue;
      }
      throw e;
    }
  }
  
  throw new A2AInternalError('Internal error after max retries');
}
```

---

### 2.6 A2A 特定错误码详解

#### -32001 TaskNotFound

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

#### -32002 TaskCancelled

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

#### -32003 TaskExpired

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

#### -32004 InvalidContext

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32004,
    "message": "Invalid context",
    "data": {
      "context_id": "ctx-xyz789",
      "reason": "expired",
      "valid_contexts": ["ctx-abc123"]
    }
  },
  "id": "req-123"
}
```

#### -32005 MessageConflict

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32005,
    "message": "Message conflict",
    "data": {
      "message_id": "msg-123456",
      "task_id": "task-abc123"
    }
  },
  "id": "req-123"
}
```

#### -32006 PartProcessingError

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32006,
    "message": "Part processing error",
    "data": {
      "part_index": 1,
      "error": "Failed to decode base64 content"
    }
  },
  "id": "req-123"
}
```

#### -32007 FileTooLarge

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32007,
    "message": "File too large",
    "data": {
      "file_size_mb": 150,
      "max_size_mb": 100
    }
  },
  "id": "req-123"
}
```

#### -32008 UnsupportedFormat

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32008,
    "message": "Unsupported format",
    "data": {
      "mime_type": "application/x-xyz",
      "supported_formats": ["application/pdf", "image/png"]
    }
  },
  "id": "req-123"
}
```

#### -32009 AgentUnavailable

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32009,
    "message": "Agent unavailable",
    "data": {
      "agent_id": "agent-xyz789",
      "reason": "maintenance",
      "fallback_agents": ["agent-abc123"]
    }
  },
  "id": "req-123"
}
```

#### -32010 CapabilityNotSupported

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32010,
    "message": "Capability not supported",
    "data": {
      "requested_capability": "streaming",
      "supported_capabilities": ["text-generation"]
    }
  },
  "id": "req-123"
}
```

---

## 3. 业务层错误详解

### 3.1 Task 状态处理

#### cancelled 状态

```typescript
async function monitorTask(client: A2AClient, taskId: string): Promise<Task> {
  const eventSource = new EventSource(`${client.baseUrl}/tasks/${taskId}/subscribe`);
  
  return new Promise((resolve, reject) => {
    eventSource.onmessage = (event) => {
      const task: Task = JSON.parse(event.data);
      
      if (task.status.state === 'cancelled') {
        eventSource.close();
        reject(new A2ATaskCancelledError('Task cancelled', task.status.timestamp));
      } else if (task.status.state === 'completed') {
        eventSource.close();
        resolve(task);
      } else if (task.status.state === 'failed') {
        eventSource.close();
        reject(new A2ATaskFailedError(task.status.message?.text || 'Task failed'));
      }
    };
  });
}
```

#### failed 状态

```typescript
async function handleFailedTask(task: Task): Promise<Task | null> {
  if (task.status.state !== 'failed') return null;
  
  const errorMsg = task.status.message?.parts
    ?.filter(p => p.type === 'text')
    .map(p => p.text)
    .join('\n') || 'Unknown error';
  
  const retryable = /timeout|temporary|resource|memory|connection/i.test(errorMsg);
  
  if (retryable) {
    return recreateTask(task);
  }
  
  return null;
}
```

### 3.2 Context 管理

```typescript
class ContextManager {
  private contexts: Map<string, ConversationContext> = new Map();
  private ttlHours = 24;
  
  async getOrRefreshContext(contextId?: string): Promise<ConversationContext> {
    if (contextId) {
      const context = this.contexts.get(contextId);
      if (context && !this.isExpired(context)) {
        context.lastActivity = new Date();
        return context;
      }
      this.contexts.delete(contextId);
    }
    return this.createContext();
  }
  
  private isExpired(context: ConversationContext): boolean {
    const hoursSinceActivity = 
      (Date.now() - context.lastActivity.getTime()) / (1000 * 60 * 60);
    return hoursSinceActivity > this.ttlHours;
  }
}
```

### 3.3 文件处理

```typescript
const FILE_LIMITS = {
  maxSizeBytes: 100 * 1024 * 1024,  // 100 MB
  supportedMimeTypes: new Set([
    'application/pdf',
    'image/png',
    'image/jpeg',
    'text/plain'
  ])
};

async function processFile(filePath: string): Promise<FilePart> {
  const stats = await fs.promises.stat(filePath);
  
  if (stats.size > FILE_LIMITS.maxSizeBytes) {
    throw new A2AFileTooLargeError('File exceeds size limit', stats.size);
  }
  
  const mimeType = await detectMimeType(filePath);
  if (!FILE_LIMITS.supportedMimeTypes.has(mimeType)) {
    throw new A2AUnsupportedFormatError('Unsupported format', mimeType);
  }
  
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
```

---

## 4. 边缘情况处理

### 4.1 空 parts 数组

```typescript
function validateMessage(message: Message): void {
  if (!message.parts || message.parts.length === 0) {
    throw new A2AValidationError('Message must have at least one part');
  }
}
```

### 4.2 超大消息体

```typescript
class ChunkedUploader {
  private chunkSize = 5 * 1024 * 1024; // 5 MB
  
  async uploadLargeFile(client: A2AClient, taskId: string, filePath: string): Promise<Task> {
    const stats = await fs.promises.stat(filePath);
    const totalChunks = Math.ceil(stats.size / this.chunkSize);
    
    const uploadId = generateUploadId();
    
    for (let i = 0; i < totalChunks; i++) {
      const chunk = await this.readChunk(filePath, i);
      await client.callMethod('tasks/send', {
        task: { id: taskId },
        message: {
          role: 'user',
          parts: [{
            type: 'data',
            data: {
              type: 'file-chunk',
              value: JSON.stringify({
                uploadId,
                chunkIndex: i,
                totalChunks,
                data: chunk.toString('base64')
              })
            }
          }]
        }
      });
    }
    
    // 发送完成信号
    return client.callMethod('tasks/send', {
      task: { id: taskId },
      message: {
        role: 'user',
        parts: [{
          type: 'data',
          data: { type: 'file-chunk-complete', value: JSON.stringify({ uploadId }) }
        }]
      }
    });
  }
}
```

### 4.3 无效 base64

```typescript
function validateBase64(input: string): void {
  const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
  
  if (!base64Regex.test(input)) {
    throw new A2AValidationError('Invalid base64 format');
  }
  
  if (input.length % 4 !== 0) {
    throw new A2AValidationError('Invalid base64 length');
  }
  
  try {
    Buffer.from(input, 'base64');
  } catch {
    throw new A2AValidationError('Invalid base64 encoding');
  }
}
```

---

## 5. 完整代码示例

### 5.1 统一错误处理中间件

```typescript
class ErrorHandlingMiddleware {
  private retryableCodes = new Set([
    408, 429, 500, 502, 503, 504,
    -32603, -32009
  ]);
  
  async execute<T>(
    operation: () => Promise<T>,
    maxRetries = 3
  ): Promise<T> {
    let lastError: unknown;
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        const code = (error as A2AError).code;
        
        if (!this.retryableCodes.has(code) || attempt === maxRetries - 1) {
          break;
        }
        
        const delay = this.getDelay(attempt, error);
        await sleep(delay);
      }
    }
    
    throw lastError;
  }
  
  private getDelay(attempt: number, error: unknown): number {
    // Rate Limit 使用 Retry-After
    if ((error as A2AError).code === 429) {
      const retryAfter = (error as A2AError).data?.retry_after;
      if (retryAfter) return retryAfter * 1000;
    }
    
    // 指数退避 + 抖动
    return Math.min(
      1000 * Math.pow(2, attempt) + Math.random() * 1000,
      30000
    );
  }
}
```

### 5.2 完整客户端实现

```typescript
class RobustA2AClient {
  private middleware = new ErrorHandlingMiddleware();
  
  async callMethod<T>(method: string, params: unknown): Promise<T> {
    return this.middleware.execute(() => this.doCall<T>(method, params));
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
    
    if (!response.ok) {
      const error = await response.json();
      throw new A2AError(error.message, response.status, error.details);
    }
    
    const data = await response.json();
    
    if (data.error) {
      throw new A2AError(data.error.message, data.error.code, data.error.data);
    }
    
    return data.result;
  }
}
```

### 5.3 错误分类器

```typescript
class ErrorClassifier {
  classify(error: unknown): {
    type: string;
    retryable: boolean;
    userMessage: string;
  } {
    if (error instanceof A2ANetworkError) {
      return {
        type: 'network',
        retryable: true,
        userMessage: '网络连接问题，请检查网络后重试'
      };
    }
    
    if (error instanceof A2AAuthError) {
      return {
        type: 'auth',
        retryable: error.isTokenExpired,
        userMessage: error.isTokenExpired ? '登录已过期，请重新登录' : '认证失败'
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
        retryable: [408, 429, 500, 502, 503, 504].includes(error.code),
        userMessage: this.getUserMessage(error.code)
      };
    }
    
    return {
      type: 'unknown',
      retryable: false,
      userMessage: '发生未知错误'
    };
  }
  
  private getUserMessage(code: number): string {
    const messages: Record<number, string> = {
      400: '请求格式不正确',
      401: '未授权访问',
      403: '没有权限执行此操作',
      404: '请求的资源不存在',
      429: '请求过于频繁，请稍后重试',
      500: '服务器内部错误',
      [-32700]: '请求解析失败',
      [-32600]: '无效的请求',
      [-32601]: '方法不存在',
      [-32602]: '参数无效',
      [-32001]: '任务不存在',
      [-32002]: '任务已取消',
      [-32003]: '任务已过期'
    };
    
    return messages[code] || `错误码: ${code}`;
  }
}
```

---

## 总结

**错误处理关键点**：

1. **分层处理**：HTTP 层 → JSON-RPC 层 → 业务层
2. **幂等性**：使用 messageId 防止重复
3. **重试策略**：指数退避 + Rate Limit 特殊处理
4. **用户友好**：提供清晰的错误提示
5. **日志追踪**：记录 request_id 用于排查

**详细实现请参考主文档**：[05-error-handling.md](../../docs/05-error-handling.md)
