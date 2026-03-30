# A2A 协议故障排查手册

> 当事情不如预期时，来这里找答案

本手册提供 A2A 协议实现中常见问题的诊断和解决方案。

---

## 目录

1. [诊断流程图](#诊断流程图)
2. [常见问题 FAQ](#常见问题-faq)
3. [日志分析](#日志分析)
4. [网络问题](#网络问题)
5. [性能问题](#性能问题)
6. [调试工具](#调试工具)
7. [故障场景](#故障场景)

---

## 诊断流程图

### Agent Card 获取失败诊断

```
┌─────────────────────────────────────┐
│     Agent Card 获取失败             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  能 ping 通目标主机吗？             │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       │ No            │ Yes
       ▼               ▼
┌──────────────┐ ┌─────────────────────┐
│ 网络问题     │ │ 能 curl 443 端口？  │
│ → 检查网络   │ └──────────┬──────────┘
└──────────────┘            │
                    ┌───────┴───────┐
                    │ No            │ Yes
                    ▼               ▼
           ┌──────────────┐ ┌─────────────────────┐
           │ 防火墙/TLS   │ │ /.well-known/       │
           │ 问题         │ │ agent.json 存在？   │
           └──────────────┘ └──────────┬──────────┘
                                       │
                               ┌───────┴───────┐
                               │ No            │ Yes
                               ▼               ▼
                      ┌──────────────┐ ┌─────────────────┐
                      │ 路径错误     │ │ JSON 格式正确？ │
                      │ 或服务未配置 │ └────────┬────────┘
                      └──────────────┘          │
                                        ┌───────┴───────┐
                                        │ No            │ Yes
                                        ▼               ▼
                               ┌──────────────┐ ┌─────────────┐
                               │ JSON 解析    │ │ ✅ 成功     │
                               │ 错误         │ │ 检查字段    │
                               └──────────────┘ └─────────────┘
```

### 消息发送失败诊断

```
┌─────────────────────────────────────┐
│       消息发送失败                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  HTTP 状态码是多少？                │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┬──────────┐
    │          │          │          │
    ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────────┐
│ 4xx   │ │ 5xx   │ │ 无响应│ │ 200 但    │
│ 客户端│ │ 服务端│ │ 超时  │ │ JSON-RPC  │
│ 错误  │ │ 错误  │ │       │ │ 错误      │
└───┬───┘ └───┬───┘ └───┬───┘ └─────┬─────┘
    │         │         │           │
    ▼         ▼         ▼           ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────────┐
│检查:  │ │检查:  │ │检查:  │ │检查:      │
│认证   │ │日志   │ │网络   │ │JSON-RPC   │
│请求体 │ │服务   │ │超时   │ │协议版本   │
│路径   │ │资源   │ │重试   │ │方法名     │
└───────┘ └───────┘ └───────┘ └───────────┘
```

### SSE 流中断诊断

```
┌─────────────────────────────────────┐
│         SSE 流中断                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  立即断开还是中途断开？             │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       │ 立即          │ 中途
       ▼               ▼
┌──────────────┐ ┌─────────────────────┐
│ 检查:        │ │ 检查:               │
│ - Accept 头  │ │ - 网络稳定性        │
│ - 认证       │ │ - 服务端超时配置    │
│ - 服务端日志 │ │ - 客户端超时配置    │
└──────────────┘ │ - 心跳机制          │
                 └─────────────────────┘
```

### 认证失败诊断

```
┌─────────────────────────────────────┐
│         认证失败                    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  使用什么认证方式？                 │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────────┐
│ API   │ │ OAuth │ │ 无认证    │
│ Key   │ │ 2.0   │ │ (公开)    │
└───┬───┘ └───┬───┘ └─────┬─────┘
    │         │           │
    ▼         ▼           ▼
┌───────┐ ┌───────┐ ┌───────────┐
│检查:  │ │检查:  │ │检查:      │
│Key格式│ │Token  │ │Agent Card │
│权限   │ │有效期 │ │是否公开   │
│Header │ │Scope  │ │服务端配置 │
│位置   │ │刷新   │ │           │
└───────┘ └───────┘ └───────────┘
```

---

## 常见问题 FAQ

### Q1: "Connection refused" 怎么办？

**现象**：
```
curl: (7) Failed to connect to agent.example.com port 443: Connection refused
```

**诊断步骤**：

1. 检查目标服务是否运行
   ```bash
   # 检查端口是否监听
   curl -v telnet://agent.example.com:443
   
   # 使用 nc 测试
   nc -zv agent.example.com 443
   ```

2. 检查防火墙规则
   ```bash
   # Linux
   sudo iptables -L -n | grep 443
   sudo ufw status
   
   # 检查出站规则
   sudo iptables -L OUTPUT -n
   ```

3. 检查 DNS 解析
   ```bash
   # 确认解析到正确的 IP
   dig agent.example.com
   nslookup agent.example.com
   ```

**解决方案**：

| 原因 | 解决方案 |
|------|----------|
| 服务未启动 | 启动目标服务 |
| 端口错误 | 确认正确端口（通常 443/80） |
| 防火墙阻断 | 添加防火墙规则允许连接 |
| DNS 解析错误 | 检查 DNS 配置或使用正确 IP |

**预防措施**：
- 配置服务健康检查
- 使用负载均衡器监控服务状态
- 设置 DNS 监控告警

---

### Q2: "Timeout" 怎么办？

**现象**：
```
curl: (28) Operation timed out after 30000 milliseconds
```

**诊断步骤**：

1. 确定超时位置
   ```bash
   # 使用 verbose 模式查看超时位置
   curl -v --connect-timeout 10 --max-time 60 https://agent.example.com/
   ```

2. 检查网络延迟
   ```bash
   # 测试 RTT
   ping agent.example.com
   mtr agent.example.com
   ```

3. 检查服务端响应时间
   ```bash
   # 测量各阶段耗时
   curl -w "dns: %{time_namelookup}s\nconnect: %{time_connect}s\ntls: %{time_appconnect}s\nresponse: %{time_starttransfer}s\ntotal: %{time_total}s\n" -o /dev/null -s https://agent.example.com/
   ```

**解决方案**：

| 超时类型 | 解决方案 |
|----------|----------|
| 连接超时 | 增加连接超时时间，检查网络 |
| 读取超时 | 增加读取超时时间，优化服务端处理 |
| TLS 握手超时 | 检查证书链，优化 TLS 配置 |
| DNS 超时 | 使用备用 DNS 服务器 |

**推荐超时配置**：
```python
# A2A 客户端推荐超时配置
TIMEOUT_CONFIG = {
    "connect": 10,      # 连接超时：10秒
    "read": 60,         # 读取超时：60秒
    "total": 120,       # 总超时：120秒（包含 SSE 场景）
    "retry": 3,         # 重试次数
    "retry_delay": 1,   # 重试延迟（秒）
}
```

**预防措施**：
- 设置合理的超时时间
- 实现超时重试机制
- 监控服务响应时间

---

### Q3: "401 Unauthorized" 怎么办？

**现象**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Unauthorized",
    "data": {"http_status": 401}
  }
}
```

**诊断步骤**：

1. 检查认证信息
   ```bash
   # 验证 API Key 格式
   echo $API_KEY | head -c 20
   
   # 测试认证
   curl -H "Authorization: Bearer $API_KEY" \
        https://agent.example.com/.well-known/agent.json
   ```

2. 检查 Agent Card 中的认证配置
   ```bash
   # 查看 Agent 要求的认证方式
   curl -s https://agent.example.com/.well-known/agent.json | jq '.securitySchemes'
   ```

3. 验证 Token 有效性
   ```bash
   # 如果是 JWT，检查过期时间
   echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq '.exp'
   ```

**解决方案**：

| 认证类型 | 问题 | 解决方案 |
|----------|------|----------|
| API Key | Key 格式错误 | 检查 Key 是否完整复制 |
| API Key | Header 位置错误 | 使用正确的 Header 名称 |
| OAuth 2.0 | Token 过期 | 刷新 Token |
| OAuth 2.0 | Scope 不足 | 申请正确的权限范围 |
| 无认证 | Agent 要求认证 | 获取认证凭据 |

**正确认证示例**：
```bash
# API Key 认证
curl -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     https://agent.example.com/

# OAuth 2.0 Bearer Token
curl -H "Authorization: Bearer ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     https://agent.example.com/
```

**预防措施**：
- 实现 Token 自动刷新
- 监控 Token 过期时间
- 在 Agent Card 中清晰说明认证要求

---

### Q4: "Invalid JSON" 怎么办？

**现象**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32700,
    "message": "Parse error: Invalid JSON"
  }
}
```

**诊断步骤**：

1. 验证 JSON 语法
   ```bash
   # 使用 jq 验证
   echo 'YOUR_JSON_HERE' | jq .
   
   # 使用 Python 验证
   python3 -m json.tool your_request.json
   ```

2. 检查 Content-Type
   ```bash
   # 确认请求头正确
   curl -v -H "Content-Type: application/json" ...
   ```

3. 检查请求体编码
   ```bash
   # 查看请求体的十六进制表示
   xxd request.json | head -20
   ```

**常见 JSON 错误**：

| 错误 | 示例 | 修正 |
|------|------|------|
| 拼写错误 | `"jsonprc"` | `"jsonrpc"` |
| 缺少引号 | `{name: "test"}` | `{"name": "test"}` |
| 尾随逗号 | `{"a": 1,}` | `{"a": 1}` |
| 编码问题 | BOM 字符 | UTF-8 无 BOM |
| 转义错误 | `"text": "Hello\n"` | `"text": "Hello\\n"` |

**正确 JSON-RPC 请求格式**：
```json
{
  "jsonrpc": "2.0",
  "id": "unique-id-123",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {"kind": "text", "text": "Hello"}
      ],
      "messageId": "msg-001"
    }
  }
}
```

**预防措施**：
- 使用 JSON Schema 验证请求
- 在客户端实现请求验证
- 服务端返回详细错误信息

---

### Q5: SSE 连接立即断开怎么办？

**现象**：
```
EventSource 连接建立后立即关闭，无任何数据返回
```

**诊断步骤**：

1. 验证 SSE 支持
   ```bash
   # 检查 Agent Card
   curl -s https://agent.example.com/.well-known/agent.json | \
     jq '.capabilities.streaming'
   # 应返回 true
   ```

2. 检查请求方法
   ```bash
   # SSE 必须使用正确的 JSON-RPC 方法
   curl -N -H "Accept: text/event-stream" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":"1","method":"message/stream","params":{...}}' \
        https://agent.example.com/
   ```

3. 检查服务端响应头
   ```bash
   # 确认响应是 SSE 格式
   curl -v -N -H "Accept: text/event-stream" ... | grep -i "content-type"
   # 应该是: Content-Type: text/event-stream
   ```

**解决方案**：

| 问题 | 解决方案 |
|------|----------|
| Accept 头错误 | 添加 `Accept: text/event-stream` |
| 方法名错误 | 使用 `message/stream` 而非 `message/send` |
| 不支持流式 | 检查 Agent Card 的 streaming 能力 |
| 网络代理阻断 | 配置代理支持长连接 |
| 服务端超时配置过短 | 增加服务端超时时间 |

**正确 SSE 请求示例**：
```bash
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "jsonrpc": "2.0",
    "id": "stream-001",
    "method": "message/stream",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Hello"}],
        "messageId": "msg-001"
      }
    }
  }' \
  https://agent.example.com/
```

**预防措施**：
- 客户端实现 SSE 重连机制
- 服务端发送定期心跳事件
- 监控 SSE 连接成功率

---

## 日志分析

### 关键日志字段

A2A 实现的日志应包含以下关键字段：

| 字段名 | 描述 | 示例 |
|--------|------|------|
| `timestamp` | 时间戳 (ISO 8601) | `2024-01-15T10:30:00Z` |
| `level` | 日志级别 | `INFO`, `WARN`, `ERROR` |
| `request_id` | 请求唯一标识 | `req-abc123` |
| `method` | JSON-RPC 方法 | `message/send` |
| `agent_id` | Agent 标识 | `agent://my-agent` |
| `task_id` | 任务标识 | `task-xyz789` |
| `duration_ms` | 处理耗时 | `1234` |
| `status` | 请求状态 | `success`, `error` |
| `error_code` | 错误码 | `-32600`, `-32700` |
| `client_ip` | 客户端 IP | `192.168.1.100` |

**推荐日志格式**：
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "request_id": "req-abc123",
  "method": "message/send",
  "agent_id": "agent://my-agent",
  "task_id": "task-xyz789",
  "duration_ms": 1234,
  "status": "success",
  "client_ip": "192.168.1.100"
}
```

### 错误日志示例

#### 连接错误
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "ERROR",
  "request_id": "req-err-001",
  "error": {
    "code": "CONNECTION_REFUSED",
    "message": "Failed to connect to agent.example.com:443",
    "details": {
      "host": "agent.example.com",
      "port": 443,
      "timeout_ms": 10000
    }
  }
}
```

#### 认证错误
```json
{
  "timestamp": "2024-01-15T10:30:01.456Z",
  "level": "WARN",
  "request_id": "req-auth-001",
  "error": {
    "code": "AUTH_TOKEN_EXPIRED",
    "message": "OAuth token has expired",
    "details": {
      "token_type": "Bearer",
      "expired_at": "2024-01-15T09:00:00Z"
    }
  }
}
```

#### JSON 解析错误
```json
{
  "timestamp": "2024-01-15T10:30:02.789Z",
  "level": "ERROR",
  "request_id": "req-parse-001",
  "error": {
    "code": -32700,
    "message": "Parse error",
    "details": {
      "position": 42,
      "unexpected_char": ",",
      "context": "{...\"text\": \"hello\",}"
    }
  }
}
```

### 日志查询命令

#### 查找错误日志
```bash
# 查找所有 ERROR 级别日志
grep '"level":"ERROR"' /var/log/a2a/app.log | jq .

# 查找特定错误码
grep '"code": -32600' /var/log/a2a/app.log | jq .

# 查找特定请求的日志
grep '"request_id": "req-abc123"' /var/log/a2a/app.log | jq .
```

#### 统计错误分布
```bash
# 统计各错误码出现次数
grep '"level":"ERROR"' /var/log/a2a/app.log | \
  jq -r '.error.code' | sort | uniq -c | sort -rn

# 统计最近 1 小时错误数
find /var/log/a2a -name "*.log" -mmin -60 -exec \
  grep '"level":"ERROR"' {} \; | wc -l
```

#### 分析请求延迟
```bash
# 找出超过 5 秒的请求
grep '"duration_ms"' /var/log/a2a/app.log | \
  jq 'select(.duration_ms > 5000)'

# 计算平均响应时间
grep '"duration_ms"' /var/log/a2a/app.log | \
  jq -r '.duration_ms' | \
  awk '{sum+=$1; count++} END {print "avg:", sum/count, "ms"}'
```

### 日志分析工具

#### ELK Stack 配置示例
```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  paths:
    - /var/log/a2a/*.log
  json.keys_under_root: true
  json.message_key: log

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "a2a-logs-%{+yyyy.MM.dd}"
```

#### Grafana Loki 查询示例
```logql
# 错误日志
{app="a2a"} |= "ERROR" | json | level = "ERROR"

# 请求延迟 P99
{app="a2a"} | json | unwrap duration_ms | quantile_over_time(0.99, 1h)

# 按方法统计请求量
sum by (method) (count_over_time({app="a2a"} | json [1h]))
```

---

## 网络问题

### DNS 解析失败

**现象**：
```
curl: (6) Could not resolve host: agent.example.com
```

**诊断**：
```bash
# 测试 DNS 解析
dig agent.example.com
nslookup agent.example.com

# 检查 DNS 配置
cat /etc/resolv.conf

# 使用指定 DNS 服务器
dig @8.8.8.8 agent.example.com
```

**解决方案**：

| 问题 | 解决方案 |
|------|----------|
| DNS 服务器不可用 | 更换 DNS 服务器（8.8.8.8 或 1.1.1.1） |
| 域名不存在 | 确认域名正确，检查 Agent Card URL |
| DNS 污染/劫持 | 使用 DoH (DNS over HTTPS) |
| 本地 hosts 配置冲突 | 检查 /etc/hosts |

**临时解决**：
```bash
# 使用 IP 直连（需要正确设置 Host 头）
curl -H "Host: agent.example.com" https://1.2.3.4/

# 添加临时 hosts 条目
echo "1.2.3.4 agent.example.com" | sudo tee -a /etc/hosts
```

### 防火墙阻断

**诊断**：
```bash
# 检查出站连接
sudo iptables -L OUTPUT -n -v

# 检查是否有 DROP 规则
sudo iptables -L -n | grep DROP

# 测试特定端口
nc -zv agent.example.com 443
```

**解决方案**：
```bash
# 允许 HTTPS 出站
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# 使用 ufw
sudo ufw allow out 443/tcp
```

**企业代理环境**：
```bash
# 配置环境变量
export HTTP_PROXY="http://proxy.company.com:8080"
export HTTPS_PROXY="http://proxy.company.com:8080"
export NO_PROXY="localhost,127.0.0.1,internal.company.com"

# curl 使用代理
curl -x http://proxy.company.com:8080 https://agent.example.com/
```

### 代理配置

**HTTP 代理**：
```bash
# 环境变量方式
export HTTPS_PROXY="http://proxy.example.com:3128"

# Python requests
import os
os.environ['HTTPS_PROXY'] = 'http://proxy.example.com:3128'
```

**SOCKS 代理**：
```bash
# 通过 SSH 建立隧道
ssh -D 1080 user@jump-server

# 使用 SOCKS 代理
export ALL_PROXY="socks5://127.0.0.1:1080"
```

**代理认证**：
```bash
# 基础认证
export HTTPS_PROXY="http://user:password@proxy.example.com:3128"
```

### TLS 证书问题

**现象**：
```
curl: (60) SSL certificate problem: unable to get local issuer certificate
```

**诊断**：
```bash
# 查看证书链
openssl s_client -connect agent.example.com:443 -showcerts

# 检查证书过期时间
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
  openssl x509 -noout -dates
```

**解决方案**：

| 问题 | 解决方案 |
|------|----------|
| 证书链不完整 | 配置完整的证书链（含中间证书） |
| 自签名证书 | 导入 CA 证书到系统信任库 |
| 证书过期 | 更新证书 |
| 域名不匹配 | 使用正确的域名或更新证书 SAN |

**跳过证书验证（仅限测试）**：
```bash
# curl 跳过验证
curl -k https://agent.example.com/

# Python requests
import requests
requests.get('https://agent.example.com/', verify=False)  # 不推荐生产使用
```

---

## 性能问题

### 响应慢

**诊断**：

1. 分阶段测量
   ```bash
   curl -w "
   DNS: %{time_namelookup}s
   Connect: %{time_connect}s
   TLS: %{time_appconnect}s
   Pre-transfer: %{time_pretransfer}s
   Start-transfer: %{time_starttransfer}s
   Total: %{time_total}s
   " -o /dev/null -s https://agent.example.com/
   ```

2. 识别瓶颈
   | 阶段 | 正常值 | 异常可能原因 |
   |------|--------|--------------|
   | DNS | < 50ms | DNS 服务器慢、缓存失效 |
   | Connect | < 100ms | 网络延迟高、路由问题 |
   | TLS | < 200ms | 证书链长、服务器性能差 |
   | Start-transfer | varies | 服务端处理慢 |

3. 服务端性能分析
   ```bash
   # Python Agent 性能分析
   import cProfile
   cProfile.run('handle_request(request)')
   
   # 查看进程资源使用
   top -p $(pgrep -f a2a-agent)
   ```

**解决方案**：

| 瓶颈 | 解决方案 |
|------|----------|
| DNS 解析慢 | 使用 DNS 缓存、更换 DNS 服务器 |
| TLS 握手慢 | 启用 TLS 会话复用、优化证书链 |
| 服务端处理慢 | 优化算法、增加缓存、水平扩展 |
| 网络延迟高 | 使用 CDN、就近部署 |

### 内存泄漏

**诊断**：

1. 监控内存使用
   ```bash
   # 持续监控
   watch -n 1 'ps aux | grep a2a-agent'
   
   # 使用 valgrind 检测（C/C++ 扩展）
   valgrind --leak-check=full python a2a_agent.py
   ```

2. Python 内存分析
   ```python
   import tracemalloc
   tracemalloc.start()
   
   # ... 运行代码 ...
   
   snapshot = tracemalloc.take_snapshot()
   top_stats = snapshot.statistics('lineno')
   for stat in top_stats[:10]:
       print(stat)
   ```

**常见内存泄漏原因**：

| 原因 | 示例 | 解决方案 |
|------|------|----------|
| 未关闭连接 | 未调用 `response.close()` | 使用上下文管理器 |
| 缓存无限增长 | 简单 dict 缓存 | 使用 LRU 缓存 |
| 循环引用 | 事件监听器未移除 | 使用弱引用 |
| 大对象累积 | Task 历史记录 | 定期清理过期数据 |

**解决方案示例**：
```python
# 使用 LRU 缓存替代无限缓存
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_agent_card(agent_url: str):
    return fetch_agent_card(agent_url)

# 使用上下文管理器确保资源释放
with httpx.Client() as client:
    response = client.post(url, json=request)
    # 自动关闭连接

# 定期清理过期数据
def cleanup_old_tasks():
    cutoff = datetime.now() - timedelta(hours=24)
    Task.delete().where(Task.created_at < cutoff).execute()
```

### 连接池耗尽

**现象**：
```
httpx.PoolTimeout: No available connections
```

**诊断**：
```bash
# 查看连接状态
ss -tn | grep :443 | wc -l

# 查看 TIME_WAIT 状态连接数
ss -tn | grep TIME_WAIT | wc -l
```

**解决方案**：

1. 调整连接池大小
   ```python
   import httpx
   
   # 增加连接池大小
   client = httpx.Client(
       limits=httpx.Limits(
           max_connections=100,
           max_keepalive_connections=20,
           keepalive_expiry=30.0
       )
   )
   ```

2. 正确关闭连接
   ```python
   # 使用上下文管理器
   with httpx.Client() as client:
       response = client.get(url)
   ```

3. 系统层面调优
   ```bash
   # 增加可用端口范围
   sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
   
   # 减少 TIME_WAIT 时间
   sudo sysctl -w net.ipv4.tcp_fin_timeout=30
   ```

### CPU 飙高

**诊断**：
```bash
# 查看 CPU 使用
top -H -p $(pgrep -f a2a-agent)

# 使用 perf 分析
perf record -g -p $(pgrep -f a2a-agent) -- sleep 30
perf report
```

**常见原因**：

| 原因 | 解决方案 |
|------|----------|
| JSON 解析大文件 | 使用流式解析 |
| 正则表达式回溯 | 优化正则、限制输入长度 |
| 无限循环 | 添加超时检查 |
| 锁竞争 | 减少锁粒度、使用无锁数据结构 |

---

## 调试工具

### curl 调试命令

#### 基础调试
```bash
# 详细输出
curl -v https://agent.example.com/.well-known/agent.json

# 只显示响应头
curl -I https://agent.example.com/.well-known/agent.json

# 显示完整请求和响应
curl -v --trace-ascii /dev/stdout https://agent.example.com/
```

#### 测试认证
```bash
# Bearer Token
curl -H "Authorization: Bearer $TOKEN" https://agent.example.com/

# API Key in Header
curl -H "X-API-Key: $API_KEY" https://agent.example.com/
```

#### 测试 SSE
```bash
# 发送 SSE 请求
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/stream","params":{...}}' \
  https://agent.example.com/
```

#### 性能测试
```bash
# 测量各阶段耗时
curl -w "@curl-format.txt" -o /dev/null -s https://agent.example.com/

# curl-format.txt 内容
dns: %{time_namelookup}\n
connect: %{time_connect}\n
tls: %{time_appconnect}s\n
total: %{time_total}s\n
```

### tcpdump 抓包

#### 抓取 HTTPS 流量
```bash
# 抓取与特定主机的通信
sudo tcpdump -i any host agent.example.com -w a2a.pcap

# 抓取 443 端口
sudo tcpdump -i any port 443 -w a2a-ssl.pcap

# 实时查看
sudo tcpdump -i any port 443 -A
```

#### 过滤表达式
```bash
# 只看 SYN 包（连接建立）
sudo tcpdump 'tcp[tcpflags] & tcp-syn != 0'

# 只看 RST 包（连接重置）
sudo tcpdump 'tcp[tcpflags] & tcp-rst != 0'

# 只看 FIN 包（连接关闭）
sudo tcpdump 'tcp[tcpflags] & tcp-fin != 0'
```

### mitmproxy 分析

#### 启动代理
```bash
# 启动 mitmproxy
mitmproxy --listen-host 0.0.0.0 --listen-port 8080

# 命令行模式
mitmdump --listen-host 0.0.0.0 --listen-port 8080 -w a2a-flow.mitm
```

#### 配置客户端
```bash
# 设置代理
export HTTPS_PROXY="http://127.0.0.1:8080"

# 信任 mitmproxy 证书
# 访问 http://mitm.it 下载证书
```

#### 查看捕获的请求
```bash
# 回放分析
mitmproxy -r a2a-flow.mitm

# 导出为 HAR
mitmdump -r a2a-flow.mitm --set hardump=output.har
```

### Wireshark 过滤

#### 常用显示过滤器
```
# 过滤特定主机
ip.addr == 1.2.3.4

# 过滤 HTTP/2 流量
tcp.port == 443

# 过滤 TLS 握手
tls.handshake

# 过滤 TCP 重传
tcp.analysis.retransmission

# 过滤 TCP 零窗口
tcp.window_size == 0
```

#### 分析网络问题
```
# 查看连接建立延迟
tcp.flags.syn == 1 && tcp.flags.ack == 0

# 查看 TCP 重置
tcp.flags.reset == 1

# 查看乱序包
tcp.analysis.out_of_order
```

---

## 故障场景

### Agent 服务宕机

**现象**：
- 所有请求返回 Connection refused
- 健康检查失败

**诊断步骤**：
```bash
# 检查服务状态
systemctl status a2a-agent

# 查看进程
ps aux | grep a2a-agent

# 查看端口
ss -tlnp | grep 443

# 查看日志
journalctl -u a2a-agent -n 100
```

**解决方案**：

1. 立即恢复
   ```bash
   # 重启服务
   sudo systemctl restart a2a-agent
   
   # 如果无法启动，查看详细错误
   sudo journalctl -u a2a-agent -n 100 --no-pager
   ```

2. 排查原因
   ```bash
   # 检查 OOM
   dmesg | grep -i "out of memory"
   
   # 检查崩溃日志
   coredumpctl list
   coredumpctl info
   ```

**预防措施**：
- 配置服务自动重启：`Restart=always` in systemd unit
- 设置资源限制防止 OOM
- 实现多实例部署和负载均衡
- 配置健康检查和告警

### 数据库连接失败

**现象**：
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "error": {
    "code": -32603,
    "message": "Internal error: Database connection failed"
  }
}
```

**诊断步骤**：
```bash
# 检查数据库连通性
psql -h db.example.com -U a2a_user -d a2a_db

# 检查连接池状态
# 在应用日志中查找
grep "connection pool" /var/log/a2a/app.log

# 检查数据库连接数
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

**解决方案**：

| 问题 | 解决方案 |
|------|----------|
| 数据库不可达 | 检查网络、防火墙、DNS |
| 认证失败 | 验证用户名、密码、权限 |
| 连接池耗尽 | 增加连接池大小、检查连接泄漏 |
| 连接超时 | 增加连接超时、优化数据库性能 |

**连接池配置示例**：
```python
# SQLAlchemy 连接池
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True  # 连接前检查有效性
)
```

**预防措施**：
- 实现数据库健康检查
- 配置连接池监控
- 设置数据库连接超时和重试
- 使用读写分离分散压力

### 认证服务不可用

**现象**：
- Token 验证失败
- 无法获取新 Token

**诊断步骤**：
```bash
# 检查认证服务健康
curl https://auth.example.com/health

# 测试 Token 验证端点
curl -X POST https://auth.example.com/introspect \
  -d "token=$TOKEN"

# 检查服务日志
kubectl logs -l app=auth-service --tail=100
```

**临时解决方案**：

1. 降级策略
   ```python
   # 实现 Token 缓存
   class TokenCache:
       def __init__(self, ttl=300):
           self.cache = {}
           self.ttl = ttl
       
       def get(self, token):
           if token in self.cache:
               cached, timestamp = self.cache[token]
               if time.time() - timestamp < self.ttl:
                   return cached
           return None
       
       def set(self, token, result):
           self.cache[token] = (result, time.time())
   ```

2. 熔断器
   ```python
   from circuitbreaker import circuit
   
   @circuit(failure_threshold=5, recovery_timeout=30)
   def verify_token(token):
       return auth_client.verify(token)
   ```

**预防措施**：
- 认证服务高可用部署
- 实现 Token 本地缓存
- 配置熔断和降级策略
- 监控认证服务健康

### 第三方 API 超时

**现象**：
- Agent 响应慢或超时
- 依赖的外部服务不可用

**诊断步骤**：
```bash
# 直接测试第三方 API
curl -w "Total: %{time_total}s\n" \
     -o /dev/null -s \
     https://external-api.example.com/endpoint

# 查看依赖服务的健康状态
curl https://external-api.example.com/health
```

**解决方案**：

1. 超时配置
   ```python
   # 为每个外部调用设置合理超时
   response = httpx.get(
       external_api_url,
       timeout=httpx.Timeout(5.0, connect=2.0)
   )
   ```

2. 异步处理
   ```python
   # 使用异步任务处理慢操作
   from celery import Celery
   
   @app.task
   def call_external_api(params):
       # 异步调用外部 API
       return external_client.call(params)
   
   # 返回 Task 状态让客户端轮询
   task = call_external_api.delay(params)
   return {"taskId": task.id, "status": "processing"}
   ```

3. 缓存结果
   ```python
   # 使用缓存减少外部调用
   @cache.cached(timeout=300, key_prefix='external_data')
   def get_external_data():
       return external_client.fetch()
   ```

**预防措施**：
- 为所有外部调用设置超时
- 实现重试和退避策略
- 使用缓存减少依赖
- 监控第三方 API 可用性
- 设计降级方案

---

## 快速排查清单

遇到问题时，按此顺序检查：

```
□ 1. 网络连通性
    └─ curl -v https://agent.example.com/.well-known/agent.json

□ 2. Agent Card 可获取
    └─ curl -s https://agent.example.com/.well-known/agent.json | jq .

□ 3. 认证配置正确
    └─ 检查 API Key / Token 是否有效

□ 4. JSON 请求格式正确
    └─ 使用 jq 或 json.tool 验证

□ 5. HTTP Headers 正确
    └─ Content-Type: application/json
    └─ Accept: application/json (或 text/event-stream)

□ 6. 服务端日志
    └─ 查看 ERROR 级别日志

□ 7. 超时配置
    └─ 确认客户端和服务端超时设置

□ 8. 代理/防火墙
    └─ 检查是否需要代理配置
```

---

## 相关文档

- [01-快速上手](01-quick-start.md) - 基础使用指南
- [04-高级主题](04-advanced.md) - 高级配置和最佳实践
- [A2A 规范](https://a2a.dev/spec) - 官方协议规范

---

> 💡 **提示**: 如果本手册没有解决你的问题，请在 GitHub Issues 中提交详细的错误信息和诊断步骤。
