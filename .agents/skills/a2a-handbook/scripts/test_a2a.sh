#!/bin/bash
# A2A 协议测试脚本
# 用法: ./test_a2a.sh [server_url]

SERVER="${1:-http://127.0.0.1:8888}"

echo "========================================"
echo "A2A 协议测试"
echo "服务器: $SERVER"
echo "========================================"

# 测试 1: Agent Card
echo ""
echo "📋 测试 1: 获取 Agent Card"
echo "----------------------------------------"
curl -s "$SERVER/.well-known/agent.json" | jq .

# 测试 2: 简单消息
echo ""
echo "💬 测试 2: 发送消息"
echo "----------------------------------------"
curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "你好，A2A!"}],
        "messageId": "test-001"
      }
    }
  }' | jq .

# 测试 3: 多轮对话
echo ""
echo "🔄 测试 3: 多轮对话"
echo "----------------------------------------"
RESP1=$(curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "第一轮对话"}],
        "messageId": "msg-001"
      }
    }
  }')
CTX=$(echo "$RESP1" | jq -r '.result.contextId')
echo "第一轮响应: $(echo "$RESP1" | jq -r '.result.parts[0].text')"
echo "ContextId: $CTX"

RESP2=$(curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 3,
    \"method\": \"message/send\",
    \"params\": {
      \"message\": {
        \"role\": \"user\",
        \"parts\": [{\"kind\": \"text\", \"text\": \"第二轮对话\"}],
        \"messageId\": \"msg-002\",
        \"contextId\": \"$CTX\"
      }
    }
  }")
echo "第二轮响应: $(echo "$RESP2" | jq -r '.result.parts[0].text')"

# 测试 4: 文件上传
echo ""
echo "📁 测试 4: 文件上传"
echo "----------------------------------------"
curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {"kind": "text", "text": "请处理这个文件"},
          {"kind": "file", "file": {"name": "test.txt", "mimeType": "text/plain", "bytes": "dGVzdCBjb250ZW50"}}
        ],
        "messageId": "msg-003"
      }
    }
  }' | jq '.result.parts[0].text'

echo ""
echo "========================================"
echo "✅ 测试完成"
echo "========================================"
