# A2A Protocol Playground

一个用于交互式验证和观测 A2A 协议的单页 Web 应用。

## 功能

- 🔌 **连接配置**: 输入 Agent URL，自动获取 Agent Card
- 📋 **Agent 信息展示**: 显示 Agent 名称、描述、版本、能力和技能列表
- 💬 **消息发送**: 发送文本消息，支持多轮对话
- 📊 **可视化 JSON**: 请求/响应自动格式化并语法高亮
- 🔄 **上下文管理**: 自动维护 contextId，支持手动重置
- 📝 **自定义 JSON**: 支持发送自定义 JSON-RPC 请求

## 使用方法

### 1. 启动 A2A Agent 服务

确保你的 A2A Agent 服务已启动，例如：

```bash
# 使用 Python 示例服务
cd ../python
python full_server.py
```

服务将在 `http://127.0.0.1:8888` 启动。

### 2. 打开 Playground

直接在浏览器中打开 `index.html` 文件：

```bash
# macOS
open index.html

# Linux
xdg-open index.html

# Windows
start index.html
```

或者使用 Python 启动简单的 HTTP 服务器：

```bash
python -m http.server 8080
# 然后访问 http://localhost:8080
```

### 3. 连接 Agent

1. 在 "Agent URL" 输入框中填写 Agent 地址（默认 `http://127.0.0.1:8888`）
2. 点击 "获取 Agent Card" 按钮
3. 左侧面板将显示 Agent 的详细信息

### 4. 发送消息

1. 在底部文本框中输入消息内容
2. 点击 "发送消息" 或按 `Ctrl+Enter`
3. 观察右侧消息历史区域的请求和响应

## 界面说明

```
┌─────────────────────────────────────────────────────────────┐
│                   A2A Protocol Playground                   │
├──────────────────┬──────────────────────────────────────────┤
│  连接配置        │  状态: ● 已连接  Context: abc123...      │
│  Agent URL       ├──────────────────────────────────────────┤
│  [获取Agent Card]│  ┌─ 请求 ─────────────────────────────┐  │
│                  │  │ { "method": "message/send", ... }  │  │
│  Agent 信息      │  └────────────────────────────────────┘  │
│  名称: My Agent  │  ┌─ 响应 ─────────────────────────────┐  │
│  描述: ...       │  │ { "result": { "parts": [...] } }   │  │
│  技能: [echo]    │  └────────────────────────────────────┘  │
│                  │                                          │
│  快速参考        ├──────────────────────────────────────────┤
│  GET /.well-known│  [输入消息...]              [发送消息]   │
└──────────────────┴──────────────────────────────────────────┘
```

## 注意事项

### CORS 问题

如果 Agent 服务没有配置 CORS，浏览器会阻止跨域请求。解决方法：

1. **修改 Agent 服务**（推荐）：
   ```python
   from flask_cors import CORS
   app = Flask(__name__)
   CORS(app)
   ```

2. **使用浏览器扩展**：安装 CORS Unblock 等扩展

3. **使用 HTTP 服务器**：将 `index.html` 放在 Agent 服务的静态文件目录

### 仅支持 HTTP

由于浏览器的安全限制，WebSocket 和 SSE 流式响应需要额外处理。当前版本仅支持 HTTP 请求。

## 自定义开发

修改 `index.html` 中的 JavaScript 代码以添加新功能：

- 添加新的 JSON-RPC 方法调用
- 支持文件上传/下载
- 集成 OAuth 认证
- 添加请求/响应的保存和导出

## 相关链接

- [A2A 协议文档](../../docs/01-quick-start.md)
- [Python 示例](../python/)
- [cURL 示例](../curl/)
