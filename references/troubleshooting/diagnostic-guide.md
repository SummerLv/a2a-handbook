# A2A 详细诊断指南

> 故障排查的完整流程与深度分析

---

## 目录

- [诊断方法论](#诊断方法论)
- [分层诊断](#分层诊断)
- [日志分析](#日志分析)
- [网络诊断详解](#网络诊断详解)
- [性能分析](#性能分析)

---

## 诊断方法论

### 诊断原则

1. **从外向内**: 网络 → 服务 → 应用 → 代码
2. **先简后繁**: 先检查配置，再看代码逻辑
3. **最小复现**: 简化问题场景，定位根因
4. **日志优先**: 查看日志，减少猜测

### 诊断流程图

```
问题发生
    ↓
复现问题 → 确认问题存在
    ↓
查看日志 → 找到错误信息
    ↓
分层诊断 → 定位问题层
    ↓
假设验证 → 确认根因
    ↓
实施修复 → 验证解决
    ↓
文档记录 → 防止复发
```

---

## 分层诊断

### Layer 1: 网络层

**症状**: 连接失败、超时、DNS错误

**诊断工具**:
```bash
# 1. 基础连通性
ping agent.example.com
traceroute agent.example.com

# 2. 端口可达性
nc -zv agent.example.com 443
telnet agent.example.com 443

# 3. DNS解析
dig agent.example.com
nslookup agent.example.com
host agent.example.com

# 4. 抓包分析
sudo tcpdump -i any host agent.example.com -w a2a.pcap
sudo tcpdump -i any port 443 -A

# 5. 查看路由
ip route get $(dig +short agent.example.com)
```

**常见问题**:

| 问题 | 症状 | 解决方案 |
|------|------|----------|
| DNS污染 | 解析到错误IP | 使用可信DNS或DoH |
| 防火墙阻断 | 连接超时 | 检查iptables规则 |
| 路由问题 | 不可达 | 检查路由表 |
| MTU问题 | 大包丢失 | 调整MTU或启用PMTU |

### Layer 2: TLS 层

**症状**: 证书错误、握手失败

**诊断工具**:
```bash
# 1. 查看证书链
openssl s_client -connect agent.example.com:443 -showcerts

# 2. 检查证书详情
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
     openssl x509 -noout -text

# 3. 检查证书过期
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
     openssl x509 -noout -dates

# 4. 验证证书链
openssl verify -CAfile ca-bundle.crt cert.pem

# 5. 测试TLS版本
openssl s_client -connect agent.example.com:443 -tls1_2
openssl s_client -connect agent.example.com:443 -tls1_3

# 6. 测试加密套件
nmap --script ssl-enum-ciphers -p 443 agent.example.com
```

**常见问题**:

| 问题 | 症状 | 解决方案 |
|------|------|----------|
| 证书过期 | `certificate has expired` | 更新证书 |
| 证书链不完整 | `unable to verify` | 配置完整证书链 |
| 自签名证书 | `self signed certificate` | 导入CA到信任库 |
| 域名不匹配 | `certificate name mismatch` | 更新证书SAN |
| TLS版本过低 | `protocol version` | 升级TLS版本 |

### Layer 3: HTTP 层

**症状**: 4xx/5xx错误、认证失败

**诊断工具**:
```bash
# 1. 查看HTTP头
curl -I https://agent.example.com/.well-known/agent.json
curl -v https://agent.example.com/.well-known/agent.json

# 2. 测试认证
curl -H "Authorization: Bearer $TOKEN" \
     -v https://agent.example.com/.well-known/agent.json

# 3. 测试不同HTTP方法
curl -X POST -H "Content-Type: application/json" \
     -d '{"test":"data"}' https://agent.example.com/

# 4. 跟踪重定向
curl -L -v https://agent.example.com/

# 5. 查看响应时间
curl -w "total:%{time_total}s\n" -o /dev/null -s \
     https://agent.example.com/.well-known/agent.json
```

**HTTP状态码分类**:

| 状态码 | 含义 | 常见原因 |
|--------|------|----------|
| 400 | Bad Request | 请求格式错误 |
| 401 | Unauthorized | 认证失败 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 路径错误 |
| 405 | Method Not Allowed | 方法不支持 |
| 429 | Too Many Requests | 限流 |
| 500 | Internal Server Error | 服务端错误 |
| 502 | Bad Gateway | 上游服务错误 |
| 503 | Service Unavailable | 服务不可用 |
| 504 | Gateway Timeout | 上游超时 |

### Layer 4: JSON-RPC 层

**症状**: 协议错误、方法调用失败

**诊断工具**:
```bash
# 1. 验证JSON格式
echo '{"jsonrpc":"2.0","id":"1","method":"test"}' | jq .

# 2. 发送测试请求
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"1","method":"agent/card","params":{}}' \
     https://agent.example.com/

# 3. 检查响应格式
curl -s -X POST \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"1","method":"agent/card","params":{}}' \
     https://agent.example.com/ | jq .
```

**JSON-RPC错误码**:

| 错误码 | 含义 | 原因 |
|--------|------|------|
| -32700 | Parse error | JSON解析失败 |
| -32600 | Invalid Request | 请求对象无效 |
| -32601 | Method not found | 方法不存在 |
| -32602 | Invalid params | 参数无效 |
| -32603 | Internal error | 服务端内部错误 |

---

## 日志分析

### 日志位置

```bash
# 系统日志
/var/log/syslog
/var/log/messages

# 应用日志
/var/log/a2a-agent/app.log
/var/log/a2a-agent/error.log

# Journalctl日志
journalctl -u a2a-agent
```

### 日志分析技巧

```bash
# 1. 查看最近错误
journalctl -u a2a-agent -p err -n 100

# 2. 实时查看日志
journalctl -u a2a-agent -f

# 3. 按时间范围
journalctl -u a2a-agent --since "2024-01-01" --until "2024-01-02"

# 4. 搜索关键词
journalctl -u a2a-agent | grep -i "error\|fail\|exception"

# 5. 统计错误类型
journalctl -u a2a-agent | grep ERROR | awk '{print $NF}' | sort | uniq -c

# 6. 查看错误上下文
journalctl -u a2a-agent -B -A 10 | grep -A 10 -B 10 "ERROR"
```

### 常见日志模式

```
# 网络错误
Connection refused → 服务未启动或端口错误
Connection timeout → 网络问题或防火墙

# 认证错误
Invalid token → Token过期或格式错误
Permission denied → 权限不足

# JSON错误
Parse error: Expecting ',' delimiter → JSON格式错误
Invalid JSON-RPC request → 缺少必要字段

# 性能问题
Slow query detected → 数据库查询慢
Memory usage high → 内存泄漏

# 服务错误
OOM killed → 内存不足
Segmentation fault → 程序崩溃
```

---

## 网络诊断详解

### DNS 问题诊断

```bash
# 1. 测试不同DNS服务器
dig @8.8.8.8 agent.example.com
dig @1.1.1.1 agent.example.com

# 2. 查看DNS缓存
# Linux
sudo systemd-resolve --statistics

# macOS
sudo dscacheutil -statistics

# 3. 清除DNS缓存
# Linux
sudo systemd-resolve --flush-caches

# macOS
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder

# 4. 使用DoH
curl -H "accept: application/dns-json" \
     "https://dns.google/resolve?name=agent.example.com&type=A"
```

### 防火墙问题诊断

```bash
# 1. 查看iptables规则
sudo iptables -L -n -v

# 2. 查看NAT规则
sudo iptables -t nat -L -n -v

# 3. 查看连接跟踪
sudo conntrack -L

# 4. 测试特定端口
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT

# 5. 查看防火墙日志
sudo tail -f /var/log/iptables.log
```

### 代理问题诊断

```bash
# 1. 检查代理配置
env | grep -i proxy

# 2. 测试代理
curl -x http://proxy.example.com:8080 \
     https://agent.example.com/.well-known/agent.json

# 3. 检查代理环境变量
echo $HTTP_PROXY
echo $HTTPS_PROXY
echo $NO_PROXY
```

---

## 性能分析

### 响应时间分析

```bash
# 1. 详细时间分解
curl -w "\
dns: %{time_namelookup}s\n\
connect: %{time_connect}s\n\
tls: %{time_appconnect}s\n\
pretransfer: %{time_pretransfer}s\n\
starttransfer: %{time_starttransfer}s\n\
total: %{time_total}s\n\
" -o /dev/null -s https://agent.example.com/

# 2. 并发测试
ab -n 1000 -c 10 https://agent.example.com/.well-known/agent.json

# 3. 持续监控
watch -n 1 'curl -w "total:%{time_total}s\n" -o /dev/null -s https://agent.example.com/'
```

### 性能瓶颈识别

| 指标 | 正常范围 | 异常处理 |
|------|----------|----------|
| DNS解析 | < 50ms | 更换DNS服务器 |
| TCP连接 | < 100ms | 检查网络延迟 |
| TLS握手 | < 200ms | 优化证书链 |
| 首字节 | < 500ms | 优化服务端 |
| 总时间 | < 1s | 综合优化 |

### 资源监控

```bash
# 1. CPU监控
top -p $(pgrep -f a2a-agent)

# 2. 内存监控
ps aux | grep a2a-agent
pmap -x $(pgrep -f a2a-agent)

# 3. 连接监控
ss -tnp | grep :443
netstat -anp | grep :443

# 4. 文件描述符
lsof -p $(pgrep -f a2a-agent) | wc -l
```

---

## 参考资源

- [网络问题详解](network-issues.md)
- [监控配置](monitoring-config.md)
- [性能优化指南](performance-optimization.md)
