# A2A 监控配置指南

> 完整的监控方案与告警配置

---

## 目录

- [监控架构](#监控架构)
- [指标采集](#指标采集)
- [日志收集](#日志收集)
- [告警配置](#告警配置)
- [仪表板配置](#仪表板配置)

---

## 监控架构

### 推荐技术栈

```
┌─────────────────────────────────────────┐
│          Grafana (可视化)                │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│        Prometheus (指标存储)             │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│    Exporter (指标采集)                   │
│    ├─ Node Exporter (系统指标)           │
│    ├─ Blackbox Exporter (探针)          │
│    └─ Custom Exporter (应用指标)         │
└─────────────────────────────────────────┘
```

### 监控维度

| 维度 | 指标 | 工具 |
|------|------|------|
| 基础设施 | CPU、内存、磁盘、网络 | Node Exporter |
| 应用性能 | 响应时间、QPS、错误率 | APM |
| 业务指标 | Agent调用次数、成功率 | Custom Exporter |
| 可用性 | 端点可达性、证书过期 | Blackbox Exporter |

---

## 指标采集

### Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # 系统指标
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']

  # A2A Agent 探针
  - job_name: 'a2a-probe'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://agent1.example.com/.well-known/agent.json
          - https://agent2.example.com/.well-known/agent.json
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9115

  # 应用指标
  - job_name: 'a2a-agent'
    static_configs:
      - targets: ['localhost:8080']
```

### Node Exporter 安装

```bash
# 下载
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.0/node_exporter-1.6.0.linux-amd64.tar.gz
tar xzf node_exporter-1.6.0.linux-amd64.tar.gz

# 运行
./node_exporter

# systemd服务
cat > /etc/systemd/system/node_exporter.service <<EOF
[Unit]
Description=Node Exporter

[Service]
ExecStart=/usr/local/bin/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

### Blackbox Exporter 配置

```yaml
# blackbox.yml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2"]
      valid_status_codes: [200]
      method: GET
      tls_config:
        insecure_skip_verify: false

  http_post_2xx:
    prober: http
    timeout: 5s
    http:
      method: POST
      headers:
        Content-Type: application/json
      body: '{"jsonrpc":"2.0","id":"1","method":"test"}'

  tcp_connect:
    prober: tcp
    timeout: 5s

  icmp:
    prober: icmp
    timeout: 5s
```

---

## 日志收集

### Loki 配置

```yaml
# loki-config.yml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2020-05-15
      store: boltdb
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 168h

storage_config:
  boltdb:
    directory: /loki/index
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
```

### Promtail 配置

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://localhost:3100/loki/api/v1/push

scrape_configs:
  - job_name: a2a-agent
    static_configs:
      - targets:
          - localhost
        labels:
          job: a2a-agent
          __path__: /var/log/a2a-agent/*.log

    pipeline_stages:
      - match:
          selector: '{job="a2a-agent"}'
          stages:
            - regex:
                expression: '^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<message>.*)$'
            - labels:
                level:
            - timestamp:
                source: timestamp
                format: "2006-01-02 15:04:05"
```

---

## 告警配置

### AlertManager 配置

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alertmanager@example.com'
  smtp_auth_username: 'alertmanager@example.com'
  smtp_auth_password: 'password'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'team-email'
  routes:
    - match:
        severity: critical
      receiver: 'team-pagerduty'
    - match:
        severity: warning
      receiver: 'team-email'

receivers:
  - name: 'team-email'
    email_configs:
      - to: 'team@example.com'

  - name: 'team-pagerduty'
    pagerduty_configs:
      - service_key: 'your-service-key'
```

### Prometheus 告警规则

```yaml
# alerts.yml
groups:
  - name: a2a-agent
    rules:
      # 可用性告警
      - alert: AgentDown
        expr: up{job="a2a-agent"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "A2A Agent {{ $labels.instance }} is down"
          description: "Agent has been down for more than 5 minutes"

      # 响应时间告警
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="a2a-agent"}[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time on {{ $labels.instance }}"
          description: "95th percentile response time is {{ $value }}s"

      # 错误率告警
      - alert: HighErrorRate
        expr: rate(http_requests_total{job="a2a-agent",status=~"5.."}[5m]) / rate(http_requests_total{job="a2a-agent"}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on {{ $labels.instance }}"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # 证书过期告警
      - alert: CertificateExpiringSoon
        expr: (ssl_cert_not_after - time()) / 86400 < 30
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Certificate expiring soon for {{ $labels.instance }}"
          description: "Certificate will expire in {{ $value }} days"

      # 内存使用告警
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is {{ $value | humanizePercentage }}"
```

---

## 仪表板配置

### Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "A2A Agent Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"a2a-agent\"}[5m])",
            "legendFormat": "{{ $labels.method }}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job=\"a2a-agent\"}[5m]))",
            "legendFormat": "p50"
          },
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job=\"a2a-agent\"}[5m]))",
            "legendFormat": "p95"
          },
          {
            "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job=\"a2a-agent\"}[5m]))",
            "legendFormat": "p99"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"a2a-agent\",status=~\"5..\"}[5m]) / rate(http_requests_total{job=\"a2a-agent\"}[5m])",
            "legendFormat": "error rate"
          }
        ]
      },
      {
        "title": "Active Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "node_netstat_Tcp_CurrEstab",
            "legendFormat": "established"
          }
        ]
      }
    ]
  }
}
```

### 推荐仪表板

| 仪表板 | 用途 | 面板 |
|--------|------|------|
| Overview | 总览视图 | QPS、延迟、错误率、可用性 |
| Infrastructure | 基础设施 | CPU、内存、磁盘、网络 |
| Business | 业务指标 | Agent调用、成功率、TOP Agent |
| Logs | 日志视图 | 错误日志、慢查询、异常模式 |

---

## 参考资源

- [Prometheus文档](https://prometheus.io/docs/)
- [Grafana文档](https://grafana.com/docs/)
- [Loki文档](https://grafana.com/docs/loki/)
