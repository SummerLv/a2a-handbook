# A2A 协议实战案例

> 真实场景的完整实现示例

## 案例目录

1. [天气 Agent](#案例1-天气-agent) - 基础查询服务
2. [旅行规划 Agent](#案例2-旅行规划-agent) - 多 Agent 协作
3. [文件处理 Agent](#案例3-文件处理-agent) - 文件上传处理
4. [长任务 Agent](#案例4-长任务-agent) - 异步任务管理
5. [电商 Agent](#案例5-电商-agent) - 复杂业务流程

---

## 案例1: 天气 Agent

### 场景描述
简单的天气查询服务，返回指定城市的天气信息。

### Agent Card
```json
{
  "name": "Weather Agent",
  "description": "Provides weather forecasts for cities worldwide",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "push_notifications": false
  },
  "skills": [{
    "id": "get_weather",
    "name": "Get Weather",
    "description": "Get current weather for a city",
    "tags": ["weather", "forecast"],
    "examples": ["What's the weather in Paris?", "北京天气怎么样"]
  }],
  "url": "https://weather-agent.example.com/"
}
```

### 服务端实现

```python
#!/usr/bin/env python3
"""天气 Agent 实现"""

import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# 模拟天气数据
WEATHER_DATA = {
    "paris": {"temp": 22, "condition": "Sunny", "humidity": 45},
    "beijing": {"temp": 28, "condition": "Cloudy", "humidity": 60},
    "tokyo": {"temp": 25, "condition": "Rainy", "humidity": 75},
    "new york": {"temp": 20, "condition": "Clear", "humidity": 50},
}

def get_weather(city: str) -> str:
    """获取天气信息"""
    city_lower = city.lower()
    if city_lower in WEATHER_DATA:
        data = WEATHER_DATA[city_lower]
        return f"{city}: {data['condition']}, {data['temp']}°C, Humidity: {data['humidity']}%"
    return f"Sorry, I don't have weather data for {city}"

class WeatherHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/.well-known/agent.json':
            self.send_json(AGENT_CARD)
    
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        
        if body['method'] == 'message/send':
            # 提取城市名
            parts = body['params']['message']['parts']
            user_text = next((p['text'] for p in parts if p['kind'] == 'text'), '')
            
            # 简单的城市提取（生产环境应使用 NLP）
            import re
            city_match = re.search(r'(?:weather in|天气)\s*(\w+)', user_text, re.I)
            city = city_match.group(1) if city_match else user_text.split()[-1]
            
            result = get_weather(city)
            
            self.send_json({
                "jsonrpc": "2.0",
                "id": body['id'],
                "result": {
                    "kind": "message",
                    "messageId": "weather-001",
                    "parts": [{"kind": "text", "text": result}],
                    "role": "agent"
                }
            })
    
    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 8080), WeatherHandler).serve_forever()
```

---

## 案例2: 旅行规划 Agent

### 场景描述
协调多个 Agent（天气、酒店、航班）完成旅行规划。

### 架构图
```
┌─────────────────────────────────────────────────────┐
│                  旅行规划 Agent                       │
│                   (Orchestrator)                     │
└─────────────────────┬───────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │ Weather │   │  Hotel  │   │  Flight │
   │  Agent  │   │  Agent  │   │  Agent  │
   └─────────┘   └─────────┘   └─────────┘
```

### 协调器实现

```python
class TravelOrchestrator:
    """旅行规划协调器"""
    
    def __init__(self):
        self.agents = {
            'weather': A2AClient("https://weather-agent.example.com"),
            'hotel': A2AClient("https://hotel-agent.example.com"),
            'flight': A2AClient("https://flight-agent.example.com"),
        }
    
    async def plan_trip(self, destination: str, dates: dict) -> dict:
        """规划旅行"""
        
        # 1. 查询天气
        weather = await self.agents['weather'].send_message(
            f"What's the weather in {destination}?"
        )
        
        # 2. 搜索酒店
        hotels = await self.agents['hotel'].send_message(
            f"Find hotels in {destination} for {dates['checkin']} to {dates['checkout']}"
        )
        
        # 3. 搜索航班
        flights = await self.agents['flight'].send_message(
            f"Find flights to {destination} on {dates['departure']}"
        )
        
        # 4. 整合结果
        return {
            "destination": destination,
            "weather": weather['result']['parts'][0]['text'],
            "hotels": hotels['result']['parts'][0]['text'],
            "flights": flights['result']['parts'][0]['text'],
            "recommendation": self._generate_recommendation(weather, hotels, flights)
        }
```

---

## 案例3: 文件处理 Agent

### 场景描述
接收文件，进行分析处理，返回结果。

### 文件处理流程
```
上传文件 → 验证格式 → 解析内容 → 处理 → 生成结果
    │          │          │         │         │
    └─ 大小检查 ─┴─ MIME检查 ─┴─ 提取数据 ─┴─ 分析/转换
```

### 实现代码

```python
import base64
import io
from pathlib import Path

class FileProcessor:
    """文件处理器"""
    
    ALLOWED_TYPES = {
        'application/pdf': self._process_pdf,
        'text/csv': self._process_csv,
        'application/json': self._process_json,
        'image/jpeg': self._process_image,
        'image/png': self._process_image,
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def process(self, file_info: dict) -> dict:
        """处理上传的文件"""
        
        # 1. 验证
        if 'bytes' not in file_info and 'uri' not in file_info:
            raise ValueError("File must have 'bytes' or 'uri'")
        
        mime_type = file_info.get('mimeType', 'application/octet-stream')
        if mime_type not in self.ALLOWED_TYPES:
            raise ValueError(f"Unsupported file type: {mime_type}")
        
        # 2. 获取内容
        if 'bytes' in file_info:
            content = base64.b64decode(file_info['bytes'])
            if len(content) > self.MAX_FILE_SIZE:
                raise ValueError(f"File too large: {len(content)} bytes")
        else:
            content = requests.get(file_info['uri']).content
        
        # 3. 处理
        processor = self.ALLOWED_TYPES[mime_type]
        result = processor(io.BytesIO(content), file_info['name'])
        
        return result
    
    def _process_pdf(self, stream, name):
        # PDF 处理逻辑
        return {"text": "PDF content extracted...", "pages": 5}
    
    def _process_csv(self, stream, name):
        # CSV 处理逻辑
        return {"rows": 100, "columns": ["A", "B", "C"]}
    
    def _process_json(self, stream, name):
        # JSON 处理逻辑
        data = json.load(stream)
        return {"keys": list(data.keys()) if isinstance(data, dict) else "array"}
    
    def _process_image(self, stream, name):
        # 图片处理逻辑
        return {"dimensions": "800x600", "format": "jpeg"}
```

---

## 案例4: 长任务 Agent

### 场景描述
执行长时间任务，支持状态查询和取消。

### 任务状态机
```
submitted → working → completed
                 ↘ input-required
                 ↘ cancelled
                 ↘ failed
```

### 实现代码

```python
import asyncio
import uuid
from typing import Dict
from dataclasses import dataclass
from enum import Enum

class TaskStatus(Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

@dataclass
class Task:
    id: str
    status: TaskStatus
    progress: int = 0
    result: dict = None
    error: str = None

class LongTaskAgent:
    """长任务 Agent"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
    
    async def create_task(self, params: dict) -> Task:
        """创建任务"""
        task_id = str(uuid.uuid4())
        task = Task(id=task_id, status=TaskStatus.SUBMITTED)
        self.tasks[task_id] = task
        
        # 异步执行任务
        asyncio.create_task(self._execute_task(task_id, params))
        
        return task
    
    async def _execute_task(self, task_id: str, params: dict):
        """执行任务"""
        task = self.tasks[task_id]
        task.status = TaskStatus.WORKING
        
        try:
            # 模拟长任务
            for i in range(10):
                if task.status == TaskStatus.CANCELLED:
                    return
                
                task.progress = (i + 1) * 10
                await asyncio.sleep(1)
            
            task.status = TaskStatus.COMPLETED
            task.result = {"message": "Task completed", "data": "..."}
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
    
    def get_task(self, task_id: str) -> Task:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> Task:
        """取消任务"""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.WORKING:
            task.status = TaskStatus.CANCELLED
        return task
```

---

## 案例5: 电商 Agent

### 场景描述
完整的电商购物流程：浏览、加购、下单、支付、查询。

### 业务流程
```
浏览商品 → 加入购物车 → 创建订单 → 支付 → 确认
    │           │           │        │       │
    └─ 搜索/筛选 ─┴─ 数量选择 ─┴─ 地址填写 ─┴─ 支付方式
```

### Skill 定义

```json
{
  "skills": [
    {
      "id": "search_products",
      "name": "Search Products",
      "description": "Search for products by keyword",
      "tags": ["search", "browse"],
      "examples": ["Find laptops under $1000", "搜索手机"]
    },
    {
      "id": "add_to_cart",
      "name": "Add to Cart",
      "description": "Add product to shopping cart",
      "tags": ["cart", "shopping"],
      "examples": ["Add this to my cart", "加购物车"]
    },
    {
      "id": "checkout",
      "name": "Checkout",
      "description": "Proceed to checkout and place order",
      "tags": ["order", "checkout"],
      "examples": ["I want to checkout", "下单"]
    },
    {
      "id": "track_order",
      "name": "Track Order",
      "description": "Track order status",
      "tags": ["order", "tracking"],
      "examples": ["Where is my order?", "订单状态"]
    }
  ]
}
```

### 多轮对话实现

```python
class ShoppingAgent:
    """电商购物 Agent"""
    
    def __init__(self):
        self.carts: Dict[str, list] = {}  # contextId -> cart
        self.orders: Dict[str, dict] = {}
    
    def handle_message(self, message: dict, context_id: str) -> dict:
        """处理购物消息"""
        
        cart = self.carts.setdefault(context_id, [])
        parts = message['parts']
        user_text = next((p['text'] for p in parts if p['kind'] == 'text'), '')
        
        # 意图识别
        if 'search' in user_text.lower() or 'find' in user_text.lower():
            return self._search_products(user_text)
        
        elif 'add' in user_text.lower() or '加购' in user_text:
            return self._add_to_cart(user_text, cart)
        
        elif 'checkout' in user_text.lower() or '下单' in user_text:
            return self._checkout(cart, context_id)
        
        elif 'order' in user_text.lower() or '订单' in user_text:
            return self._track_order(context_id)
        
        else:
            return {
                "parts": [{"kind": "text", "text": "I can help you search products, add to cart, checkout, or track orders. What would you like to do?"}],
                "role": "agent"
            }
    
    def _search_products(self, query: str) -> dict:
        # 搜索逻辑
        products = [
            {"name": "Laptop A", "price": 999},
            {"name": "Laptop B", "price": 1299},
        ]
        return {
            "parts": [
                {"kind": "text", "text": f"Found {len(products)} products:"},
                {"kind": "data", "data": products}
            ],
            "role": "agent"
        }
    
    def _add_to_cart(self, query: str, cart: list) -> dict:
        # 加购逻辑
        cart.append({"product": "Laptop A", "quantity": 1, "price": 999})
        return {
            "parts": [{"kind": "text", "text": f"Added to cart. Cart total: ${sum(item['price'] for item in cart)}"}],
            "role": "agent"
        }
    
    def _checkout(self, cart: list, context_id: str) -> dict:
        if not cart:
            return {
                "parts": [{"kind": "text", "text": "Your cart is empty. Add some products first."}],
                "role": "agent"
            }
        
        # 创建订单
        order_id = str(uuid.uuid4())[:8]
        self.orders[order_id] = {
            "items": cart,
            "total": sum(item['price'] for item in cart),
            "status": "pending_payment"
        }
        
        return {
            "parts": [{
                "kind": "text",
                "text": f"Order {order_id} created. Total: ${self.orders[order_id]['total']}. Please provide shipping address."
            }],
            "role": "agent"
        }
```

---

## 最佳实践总结

| 场景 | 建议 |
|------|------|
| **简单查询** | 使用同步 message/send |
| **多轮对话** | 使用 contextId 维护状态 |
| **文件处理** | 验证大小和类型，隔离处理 |
| **长任务** | 创建 Task，支持状态查询和取消 |
| **多 Agent 协作** | 使用 Orchestrator 模式 |
| **复杂业务** | 设计清晰的 Skill 和状态机 |
