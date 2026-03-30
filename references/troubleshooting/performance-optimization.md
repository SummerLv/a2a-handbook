# A2A 性能优化指南

> 性能瓶颈识别与优化策略

---

## 目录

- [性能分析方法](#性能分析方法)
- [网络优化](#网络优化)
- [服务端优化](#服务端优化)
- [客户端优化](#客户端优化)
- [缓存策略](#缓存策略)

---

## 性能分析方法

### 响应时间分解

```bash
# 完整时间分解
curl -w "\
dns: %{time_namelookup}s\n\
connect: %{time_connect}s\n\
tls: %{time_appconnect}s\n\
pretransfer: %{time_pretransfer}s\n\
starttransfer: %{time_starttransfer}s\n\
total: %{time_total}s\n\
size: %{size_download}B\n\
speed: %{speed_download}B/s\n\
" -o /dev/null -s https://agent.example.com/
```

### 性能基准

| 阶段 | 优秀 | 良好 | 需优化 |
|------|------|------|--------|
| DNS解析 | < 20ms | < 50ms | > 100ms |
| TCP连接 | < 50ms | < 100ms | > 200ms |
| TLS握手 | < 100ms | < 200ms | > 500ms |
| 首字节 | < 200ms | < 500ms | > 1s |
| 总时间 | < 500ms | < 1s | > 2s |

### 压测工具

```bash
# Apache Bench
ab -n 1000 -c 10 https://agent.example.com/.well-known/agent.json

# wrk
wrk -t4 -c100 -d30s https://agent.example.com/.well-known/agent.json

# hey
hey -n 1000 -c 10 https://agent.example.com/.well-known/agent.json

# vegeta
echo "GET https://agent.example.com/.well-known/agent.json" | \
  vegeta attack -duration=30s -rate=100 | \
  vegeta report
```

---

## 网络优化

### DNS 优化

```bash
# 1. 使用高速DNS服务器
# /etc/resolv.conf
nameserver 8.8.8.8
nameserver 1.1.1.1

# 2. 启用DNS缓存
# systemd-resolved
sudo systemctl enable systemd-resolved

# dnsmasq
sudo apt-get install dnsmasq
echo "cache-size=10000" | sudo tee -a /etc/dnsmasq.conf
```

### TCP 优化

```bash
# /etc/sysctl.conf
# 增加连接队列
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# 快速回收TIME_WAIT
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30

# TCP Fast Open
net.ipv4.tcp_fastopen = 3

# 应用更改
sudo sysctl -p
```

### TLS 优化

```python
# Python - 启用会话复用
import ssl

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.session_timeout = 300  # 5分钟会话缓存

# 服务端配置
# nginx
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets on;

# 启用OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
```

---

## 服务端优化

### 连接池配置

```python
# Python - httpx
import httpx

client = httpx.Client(
    limits=httpx.Limits(
        max_connections=100,          # 最大连接数
        max_keepalive_connections=20, # 保持活跃连接数
        keepalive_expiry=30           # 保持活跃超时
    ),
    timeout=httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=10.0,
        pool=5.0
    )
)
```

### 异步处理

```python
# 使用异步客户端
import httpx
import asyncio

async def fetch_agents(urls):
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return responses

# 运行
results = asyncio.run(fetch_agents(urls))
```

### 数据库优化

```python
# 连接池配置
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://user:pass@localhost/db",
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600
)

# 查询优化
# 使用索引
# 避免 N+1 查询
# 使用批量操作
```

---

## 客户端优化

### 连接复用

```python
# 错误：每次请求创建新连接
def call_agent(url):
    response = httpx.get(url)  # 每次新建连接
    return response

# 正确：复用连接
client = httpx.Client()

def call_agent(url):
    response = client.get(url)  # 复用连接
    return response

# 最佳：使用上下文管理器
def call_agents(urls):
    with httpx.Client() as client:
        return [client.get(url) for url in urls]
```

### 并发控制

```python
import asyncio
import httpx
from asyncio import Semaphore

async def fetch_with_limit(client, url, semaphore):
    async with semaphore:
        return await client.get(url)

async def fetch_all(urls, max_concurrent=10):
    semaphore = Semaphore(max_concurrent)
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_with_limit(client, url, semaphore)
            for url in urls
        ]
        return await asyncio.gather(*tasks)
```

### 超时配置

```python
# 根据场景设置超时
TIMEOUTS = {
    "quick": httpx.Timeout(5.0),           # 快速操作
    "normal": httpx.Timeout(30.0),         # 普通操作
    "long": httpx.Timeout(300.0),          # 长时间操作
    "stream": httpx.Timeout(None, read=60) # 流式响应
}

# 使用
response = client.get(url, timeout=TIMEOUTS["normal"])
```

---

## 缓存策略

### Agent Card 缓存

```python
from functools import lru_cache
import httpx

@lru_cache(maxsize=128)
def get_agent_card(url, ttl_hash=None):
    """
    缓存Agent Card
    ttl_hash: 用于控制缓存过期
    """
    response = httpx.get(f"{url}/.well-known/agent.json")
    return response.json()

def get_ttl_hash(seconds=3600):
    """生成TTL hash"""
    return int(time.time() / seconds)

# 使用
card = get_agent_card("https://agent.example.com", get_ttl_hash())
```

### Redis 缓存

```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cached_agent_card(url):
    cache_key = f"agent:card:{url}"
    
    # 尝试从缓存获取
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 缓存未命中，获取并缓存
    response = httpx.get(f"{url}/.well-known/agent.json")
    card = response.json()
    
    # 缓存1小时
    redis_client.setex(cache_key, 3600, json.dumps(card))
    
    return card
```

### HTTP 缓存头

```python
# 服务端设置缓存头
from fastapi import FastAPI, Response

app = FastAPI()

@app.get("/.well-known/agent.json")
async def get_agent_card():
    card = get_agent_card_data()
    
    return Response(
        content=json.dumps(card),
        media_type="application/json",
        headers={
            "Cache-Control": "public, max-age=3600",
            "ETag": generate_etag(card)
        }
    )

# 客户端使用ETag
def fetch_with_cache(url, etag=None):
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    
    response = httpx.get(url, headers=headers)
    
    if response.status_code == 304:
        return None  # 未修改，使用缓存
    
    return response.json(), response.headers.get("ETag")
```

---

## 性能监控

### APM 集成

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, start_http_server

REQUEST_COUNT = Counter(
    'a2a_requests_total',
    'Total A2A requests',
    ['method', 'status']
)

REQUEST_LATENCY = Histogram(
    'a2a_request_duration_seconds',
    'Request latency',
    ['method']
)

def track_request(method, status, duration):
    REQUEST_COUNT.labels(method=method, status=status).inc()
    REQUEST_LATENCY.labels(method=method).observe(duration)

# 启动metrics服务器
start_http_server(8080)
```

### 性能分析

```python
import cProfile
import pstats

def profile_function(func):
    """性能分析装饰器"""
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        
        result = func(*args, **kwargs)
        
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)
        
        return result
    return wrapper
```

---

## 参考资源

- [详细诊断指南](diagnostic-guide.md)
- [监控配置](monitoring-config.md)
- [网络问题详解](network-issues.md)
