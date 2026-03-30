# A2A 协议故障排查手册

> 快速诊断与解决常见问题

---

## 目录

- [诊断流程](#诊断流程)
- [常见问题 FAQ](#常见问题-faq)
- [快速排查清单](#快速排查清单)

---

## 诊断流程

### Agent Card 获取失败

```
网络连通 → curl 443端口 → 检查路径 → JSON格式验证
    ↓           ↓            ↓             ↓
  ping测试   防火墙/TLS   /.well-known/  jq验证
```

### 消息发送失败

```
HTTP状态码判断:
├─ 4xx → 检查认证、请求体、路径
├─ 5xx → 检查服务端日志、资源
├─ 超时 → 检查网络、超时配置
└─ JSON-RPC错误 → 检查协议版本、方法名
```

### SSE 流中断

```
立即断开 → Accept头、认证、服务端日志
中途断开 → 网络稳定性、超时配置、心跳机制
```

### 认证失败

```
API Key → 格式、权限、Header位置
OAuth 2.0 → Token有效期、Scope、刷新机制
无认证 → Agent Card公开性、服务端配置
```

---

## 常见问题 FAQ

### Q1: Connection refused

**现象**: `curl: (7) Failed to connect to port 443: Connection refused`

**诊断**:
```bash
# 检查端口监听
nc -zv agent.example.com 443

# 检查防火墙
sudo iptables -L -n | grep 443

# 检查DNS解析
dig agent.example.com
```

**解决**: 启动服务 → 确认端口 → 开放防火墙 → 修正DNS

---

### Q2: Timeout

**现象**: `curl: (28) Operation timed out`

**诊断**:
```bash
# 测量各阶段耗时
curl -w "dns:%{time_namelookup}s connect:%{time_connect}s total:%{time_total}s\n" \
     -o /dev/null -s https://agent.example.com/
```

**解决**: 
- 连接超时 → 增加超时、检查网络
- 读取超时 → 增加超时、优化服务端

**推荐配置**:
```python
TIMEOUT_CONFIG = {
    "connect": 10,   # 连接超时：10秒
    "read": 60,      # 读取超时：60秒
    "retry": 3       # 重试次数
}
```

---

### Q3: 401 Unauthorized

**现象**: JSON-RPC错误包含 `"http_status": 401`

**诊断**:
```bash
# 验证认证信息
curl -H "Authorization: Bearer $API_KEY" \
     https://agent.example.com/.well-known/agent.json

# 查看Agent要求的认证方式
curl -s https://agent.example.com/.well-known/agent.json | jq '.securitySchemes'
```

**解决**:
- API Key错误 → 检查格式、权限、Header名称
- Token过期 → 刷新Token
- Scope不足 → 申请正确权限

---

### Q4: Invalid JSON

**现象**: `{"code": -32700, "message": "Parse error"}`

**诊断**:
```bash
# 验证JSON语法
echo 'YOUR_JSON' | jq .

# 检查Content-Type
curl -v -H "Content-Type: application/json" ...
```

**常见错误**:
- 拼写错误: `"jsonprc"` → `"jsonrpc"`
- 缺少引号: `{name: "test"}` → `{"name": "test"}`
- 尾随逗号: `{"a": 1,}` → `{"a": 1}`

**解决**: 使用JSON Schema验证

---

### Q5: SSE 连接立即断开

**现象**: EventSource连接建立后立即关闭

**诊断**:
```bash
# 检查streaming能力
curl -s https://agent.example.com/.well-known/agent.json | \
     jq '.capabilities.streaming'

# 测试SSE请求
curl -N -H "Accept: text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"1","method":"message/stream","params":{...}}' \
     https://agent.example.com/
```

**解决**:
- Accept头错误 → 添加 `Accept: text/event-stream`
- 方法名错误 → 使用 `message/stream`

---

### Q6: DNS 解析失败

**现象**: `curl: (6) Could not resolve host`

**诊断**:
```bash
# 测试DNS解析
dig agent.example.com

# 检查DNS配置
cat /etc/resolv.conf

# 使用指定DNS
dig @8.8.8.8 agent.example.com
```

**解决**: 更换DNS服务器 → 确认域名正确

---

### Q7: TLS 证书问题

**现象**: `curl: (60) SSL certificate problem`

**诊断**:
```bash
# 查看证书链
openssl s_client -connect agent.example.com:443 -showcerts

# 检查证书过期
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
     openssl x509 -noout -dates
```

**解决**:
- 证书链不完整 → 配置完整证书链
- 自签名证书 → 导入CA证书
- 证书过期 → 更新证书

---

### Q8: 响应慢

**诊断**:
```bash
# 分阶段测量
curl -w "dns:%{time_namelookup}s connect:%{time_connect}s tls:%{time_appconnect}s response:%{time_starttransfer}s total:%{time_total}s\n" \
     -o /dev/null -s https://agent.example.com/
```

**瓶颈识别**:
- DNS > 50ms → DNS服务器慢
- Connect > 100ms → 网络延迟高
- TLS > 200ms → 证书链长
- Response varies → 服务端处理慢

**解决**: DNS慢→缓存 TLS慢→会话复用 服务端慢→优化

---

### Q9: 连接池耗尽

**现象**: `httpx.PoolTimeout: No available connections`

**诊断**:
```bash
# 查看连接状态
ss -tn | grep :443 | wc -l
```

**解决**:
```python
# 增加连接池
client = httpx.Client(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20
    )
)

# 使用上下文管理器
with httpx.Client() as client:
    response = client.get(url)
```

---

### Q10: 内存泄漏

**诊断**:
```bash
# 监控内存
watch -n 1 'ps aux | grep a2a-agent'
```

**常见原因**:
- 未关闭连接 → 使用上下文管理器
- 缓存无限增长 → 使用LRU缓存
- 大对象累积 → 定期清理

---

### Q11: Agent 服务宕机

**诊断**:
```bash
# 检查服务状态
systemctl status a2a-agent

# 查看日志
journalctl -u a2a-agent -n 100
```

**解决**:
- 重启服务: `sudo systemctl restart a2a-agent`
- 检查OOM: `dmesg | grep -i "out of memory"`

---

### Q12: 数据库连接失败

**现象**: `Internal error: Database connection failed`

**诊断**:
```bash
# 检查数据库连通性
psql -h db.example.com -U a2a_user -d a2a_db
```

**解决**:
- 数据库不可达 → 检查网络、防火墙
- 连接池耗尽 → 增加连接池大小

---

### Q13: 第三方 API 超时

**诊断**:
```bash
# 直接测试API
curl -w "Total: %{time_total}s\n" -o /dev/null -s \
     https://external-api.example.com/endpoint
```

**解决**:
```python
# 设置超时
response = httpx.get(url, timeout=httpx.Timeout(5.0, connect=2.0))

# 使用缓存
@cache.cached(timeout=300)
def get_external_data():
    return external_client.fetch()
```

---

## 快速排查清单

```
□ 1. 网络连通性
    └─ curl -v https://agent.example.com/.well-known/agent.json

□ 2. Agent Card 可获取
    └─ curl -s https://agent.example.com/.well-known/agent.json | jq .

□ 3. 认证配置正确
    └─ 检查 API Key / Token 有效性

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

## 调试工具速查

```bash
# 基础调试
curl -v https://agent.example.com/.well-known/agent.json

# 认证测试
curl -H "Authorization: Bearer $TOKEN" https://agent.example.com/

# SSE测试
curl -N -H "Accept: text/event-stream" https://agent.example.com/

# 性能测试
curl -w "dns:%{time_namelookup}s\nconnect:%{time_connect}s\ntotal:%{time_total}s\n" \
     -o /dev/null -s https://agent.example.com/

# 网络诊断
dig agent.example.com
nc -zv agent.example.com 443

# 服务诊断
systemctl status a2a-agent
journalctl -u a2a-agent -n 100

# JSON验证
echo 'YOUR_JSON' | jq .

# 证书检查
openssl s_client -connect agent.example.com:443 -showcerts
```

---

## 参考资源

- 📖 [详细诊断指南](../references/troubleshooting/diagnostic-guide.md) - 完整诊断流程
- 📊 [监控配置](../references/troubleshooting/monitoring-config.md) - 完整监控方案
- 🌐 [网络问题详解](../references/troubleshooting/network-issues.md) - 网络层排查
- ⚡ [性能优化指南](../references/troubleshooting/performance-optimization.md) - 性能调优
- 📝 [01-快速上手](01-quick-start.md) - 基础使用指南
- 🔧 [06-高级主题](04-advanced.md) - 高级配置

---

> 💡 **提示**: 如果本手册没有解决你的问题，请在 GitHub Issues 中提交详细的错误信息和诊断步骤。
