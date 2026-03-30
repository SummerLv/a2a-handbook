# A2A 网络问题详解

> 网络层故障的深度分析与解决方案

---

## 目录

- [DNS 问题](#dns-问题)
- [防火墙问题](#防火墙问题)
- [TLS/SSL 问题](#tlsssl-问题)
- [代理问题](#代理问题)
- [网络性能问题](#网络性能问题)

---

## DNS 问题

### DNS 解析失败

**现象**: `curl: (6) Could not resolve host`

**诊断步骤**:
```bash
# 1. 测试DNS解析
dig agent.example.com
dig +short agent.example.com

# 2. 检查DNS配置
cat /etc/resolv.conf

# 3. 测试不同DNS服务器
dig @8.8.8.8 agent.example.com
dig @1.1.1.1 agent.example.com

# 4. 检查hosts文件
cat /etc/hosts | grep agent.example.com

# 5. 测试DNS over HTTPS
curl -H "accept: application/dns-json" \
     "https://dns.google/resolve?name=agent.example.com&type=A"
```

**常见原因与解决方案**:

| 原因 | 诊断方法 | 解决方案 |
|------|----------|----------|
| DNS服务器不可达 | ping 8.8.8.8 | 更换DNS服务器 |
| DNS污染 | dig结果不一致 | 使用DoH或VPN |
| 域名不存在 | dig返回NXDOMAIN | 确认域名正确 |
| 本地hosts覆盖 | 检查/etc/hosts | 删除或更新hosts条目 |

### DNS 解析慢

**诊断**:
```bash
# 测量DNS解析时间
dig agent.example.com | grep "Query time"

# 持续监控
for i in {1..10}; do
    dig agent.example.com | grep "Query time"
done
```

**优化方案**:
```bash
# 1. 使用更快的DNS服务器
# 编辑 /etc/resolv.conf
nameserver 8.8.8.8
nameserver 1.1.1.1

# 2. 启用DNS缓存
# systemd-resolved
sudo systemctl enable systemd-resolved
sudo systemctl start systemd-resolved

# 3. 使用dnsmasq
sudo apt-get install dnsmasq
echo "cache-size=1000" | sudo tee -a /etc/dnsmasq.conf
sudo systemctl restart dnsmasq
```

### DNS 缓存问题

**现象**: 域名IP变更后仍解析到旧IP

**解决方案**:
```bash
# Linux - systemd-resolved
sudo systemd-resolve --flush-caches

# Linux - nscd
sudo systemctl restart nscd

# macOS
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder

# Windows
ipconfig /flushdns

# 浏览器缓存
# Chrome: chrome://net-internals/#dns
# Firefox: about:networking#dns
```

---

## 防火墙问题

### 连接被阻断

**现象**: `Connection timed out` 或 `Connection refused`

**诊断步骤**:
```bash
# 1. 测试端口连通性
nc -zv agent.example.com 443
telnet agent.example.com 443

# 2. 查看本地防火墙规则
sudo iptables -L -n -v
sudo ufw status

# 3. 查看NAT规则
sudo iptables -t nat -L -n -v

# 4. 查看连接跟踪
sudo conntrack -L | grep 443

# 5. 抓包分析
sudo tcpdump -i any host agent.example.com and port 443
```

**解决方案**:

```bash
# iptables放行
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -I OUTPUT -p tcp --sport 443 -j ACCEPT

# ufw放行
sudo ufw allow 443/tcp

# firewalld放行
sudo firewall-cmd --add-port=443/tcp --permanent
sudo firewall-cmd --reload
```

### 出站连接被阻止

**现象**: 客户端无法连接外部Agent

**诊断**:
```bash
# 测试出站连接
curl -v https://agent.example.com/.well-known/agent.json

# 查看出站规则
sudo iptables -L OUTPUT -n -v

# 查看NAT规则
sudo iptables -t nat -L -n -v
```

**解决方案**:
```bash
# 允许出站HTTPS
sudo iptables -I OUTPUT -p tcp --dport 443 -j ACCEPT

# 配置SNAT（如果需要）
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

---

## TLS/SSL 问题

### 证书验证失败

**现象**: `curl: (60) SSL certificate problem`

**诊断步骤**:
```bash
# 1. 查看证书详情
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
     openssl x509 -noout -text

# 2. 查看证书链
openssl s_client -connect agent.example.com:443 -showcerts

# 3. 验证证书
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt cert.pem

# 4. 检查证书过期
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
     openssl x509 -noout -dates

# 5. 检查域名匹配
echo | openssl s_client -connect agent.example.com:443 2>/dev/null | \
     openssl x509 -noout -text | grep -A1 "Subject Alternative Name"
```

**常见问题**:

| 问题 | 错误信息 | 解决方案 |
|------|----------|----------|
| 证书过期 | `certificate has expired` | 更新证书 |
| 域名不匹配 | `certificate name mismatch` | 添加SAN或使用正确域名 |
| 自签名证书 | `self signed certificate` | 导入CA到信任库 |
| 证书链不完整 | `unable to verify` | 配置完整证书链 |
| 根CA不受信任 | `unable to get local issuer` | 更新CA证书库 |

### TLS 版本不兼容

**现象**: `sslv3 alert handshake failure`

**诊断**:
```bash
# 测试不同TLS版本
openssl s_client -connect agent.example.com:443 -tls1
openssl s_client -connect agent.example.com:443 -tls1_1
openssl s_client -connect agent.example.com:443 -tls1_2
openssl s_client -connect agent.example.com:443 -tls1_3

# 查看支持的加密套件
nmap --script ssl-enum-ciphers -p 443 agent.example.com
```

**解决方案**:
```python
# Python - 指定TLS版本
import ssl
import httpx

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.minimum_version = ssl.TLSVersion.TLSv1_2

client = httpx.Client(verify=context)
```

---

## 代理问题

### 代理配置

**诊断**:
```bash
# 查看代理环境变量
env | grep -i proxy

# 测试代理连接
curl -x http://proxy.example.com:8080 \
     https://agent.example.com/.well-known/agent.json

# 查看代理设置
git config --global http.proxy
npm config get proxy
```

**配置代理**:
```bash
# 环境变量
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1

# Git
git config --global http.proxy http://proxy.example.com:8080

# npm
npm config set proxy http://proxy.example.com:8080
npm config set https-proxy http://proxy.example.com:8080

# Python requests
import os
os.environ['HTTP_PROXY'] = 'http://proxy.example.com:8080'
```

### 代理认证失败

**现象**: `407 Proxy Authentication Required`

**解决方案**:
```bash
# curl
curl -x http://user:pass@proxy.example.com:8080 \
     https://agent.example.com/

# 环境变量
export HTTP_PROXY=http://user:pass@proxy.example.com:8080
```

---

## 网络性能问题

### 高延迟

**诊断**:
```bash
# 1. 测量RTT
ping -c 10 agent.example.com

# 2. 路由追踪
traceroute agent.example.com
mtr agent.example.com

# 3. 测量各阶段耗时
curl -w "dns:%{time_namelookup}s connect:%{time_connect}s total:%{time_total}s\n" \
     -o /dev/null -s https://agent.example.com/
```

**优化方案**:
- 使用CDN加速
- 启用TCP Fast Open
- 优化网络路由
- 使用地理位置更近的服务器

### 带宽限制

**诊断**:
```bash
# 测量下载速度
curl -o /dev/null -w "speed:%{speed_download}B/s\n" \
     https://agent.example.com/large-file

# 持续监控
iftop -i eth0
nload
```

### 连接数限制

**现象**: `Too many open files` 或 `Connection refused`

**诊断**:
```bash
# 查看当前连接数
ss -tn | wc -l

# 查看文件描述符限制
ulimit -n

# 查看TIME_WAIT状态
ss -tn | grep TIME_WAIT | wc -l
```

**优化方案**:
```bash
# 增加文件描述符限制
ulimit -n 65535

# 永久设置 - /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535

# 优化TCP参数
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=8192
```

---

## 参考资源

- [详细诊断指南](diagnostic-guide.md)
- [监控配置](monitoring-config.md)
- [性能优化指南](performance-optimization.md)
