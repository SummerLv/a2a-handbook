# A2A Handbook

> 面向开发者的 A2A (Agent-to-Agent) 协议完整指南

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol-blue)](https://a2a-protocol.org/)

## 🌟 项目特色

- 📚 **完整文档** - 从快速上手到生产部署
- 💻 **可运行代码** - Python 服务端/客户端示例
- 🔒 **安全指南** - 攻击场景与防御措施
- 🧪 **测试用例** - 覆盖正常/异常场景
- 🎯 **实战案例** - 5 个真实业务场景
- 💡 **面试问答** - 技术深度解析

## 什么是 A2A？

A2A (Agent-to-Agent) 是由 Google 发起的开放协议，让不同 AI Agent 之间能够：
- **互相发现** - 通过 Agent Card 声明能力
- **安全通信** - 基于 JSON-RPC 2.0 over HTTP
- **协作完成任务** - 多轮对话、流式响应、文件传输

## 5 分钟快速上手

### 1. 获取 Agent Card

```bash
curl https://hello-world-gxfr.onrender.com/.well-known/agent.json
```

### 2. 发送消息

```bash
curl -X POST https://hello-world-gxfr.onrender.com/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "hello"}],
        "messageId": "test-001"
      }
    }
  }'
```

## 核心概念

| 概念 | 说明 |
|------|------|
| **Agent Card** | Agent 的"名片"，声明能力和端点 |
| **JSON-RPC** | 通信协议，方法包括 `message/send`, `message/stream` 等 |
| **Task** | 任务对象，有生命周期（submitted → working → completed） |
| **Part** | 消息内容单元，支持 text/file/data 三种类型 |

## 📁 项目结构

```
a2a-handbook/
├── docs/                       # 📚 完整文档
│   ├── 01-quick-start.md      # 5分钟快速上手
│   ├── 02-core-concepts.md    # 核心概念详解
│   ├── 03-examples.md         # 代码示例
│   ├── 04-advanced.md         # 进阶：认证、安全、部署
│   ├── 05-scenarios.md        # 场景全景图
│   ├── 06-security-guide.md   # 🔒 安全指南
│   ├── 07-interview-qa.md     # 💡 面试问答
│   ├── 08-troubleshooting.md  # 🔧 故障排查
│   └── 09-practice-cases.md   # 🎯 实战案例
├── examples/                   # 💻 可运行代码
│   ├── python/
│   │   ├── full_server.py     # 完整服务端
│   │   ├── client.py          # 完整客户端
│   │   ├── error_demo.py      # 异常演示
│   │   ├── security_demo.py   # 安全演示
│   │   └── test_client.py     # 测试客户端
│   └── curl/
│       └── requests.sh        # cURL 测试脚本
├── tests/                      # 🧪 测试用例
│   └── test_cases.py
├── checklists/                 # ✅ 检查清单
│   └── deployment-checklist.md
└── .agents/skills/a2a-handbook/ # 🎮 交互式 Skill
    ├── SKILL.md               # 主入口
    ├── skills/
    │   ├── learn/SKILL.md     # /a2a-learn
    │   ├── practice/SKILL.md  # /a2a-practice
    │   ├── debug/SKILL.md     # /a2a-debug
    │   └── build/SKILL.md     # /a2a-build
    └── references/
        └── protocol-spec.md   # 协议规范
```

## 使用 Skill

本项目提供交互式 Skill，在 OpenClaw / Claude Code 中使用：

```bash
# 安装
git clone https://github.com/yourname/a2a-handbook.git ~/.claude/skills/a2a-handbook

# 使用
/a2a-learn      # 学习 A2A 协议
/a2a-practice   # 实践：启动本地服务
/a2a-debug      # 调试：分析 A2A 流量
/a2a-build      # 构建：生成服务端/客户端代码
```

## 资源

- [官方规范](https://github.com/google/A2A)
- [官方文档](https://google.github.io/A2A/)
- [A2A Registry](https://a2aregistry.in/)

## License

MIT
