#!/bin/bash
# A2A 协议完整测试脚本
# 用法: ./requests.sh [server_url]

set -e

SERVER="${1:-http://127.0.0.1:8888}"
echo "=========================================="
echo "A2A 协议完整测试"
echo "服务器: $SERVER"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Agent Card
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}📋 测试 1: 获取 Agent Card${NC}"
echo -e "${BLUE}========================================${NC}"
curl -s "$SERVER/.well-known/agent.json" | jq '{
  name,
  version,
  capabilities,
  skills: [.skills[].id]
}'

# 2. 简单消息
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}💬 测试 2: 发送简单消息${NC}"
echo -e "${BLUE}========================================${NC}"
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
  }' | jq '.result'

# 3. 多轮对话
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}🔄 测试 3: 多轮对话${NC}"
echo -e "${BLUE}========================================${NC}"

# 第一轮
RESP1=$(curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
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
echo -e "${GREEN}第一轮响应:${NC} $(echo "$RESP1" | jq -r '.result.parts[0].text')"
echo -e "${GREEN}ContextId:${NC} $CTX"

# 第二轮
RESP2=$(curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 2,
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
echo -e "${GREEN}第二轮响应:${NC} $(echo "$RESP2" | jq -r '.result.parts[0].text')"

# 第三轮
RESP3=$(curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 3,
    \"method\": \"message/send\",
    \"params\": {
      \"message\": {
        \"role\": \"user\",
        \"parts\": [{\"kind\": \"text\", \"text\": \"第三轮对话\"}],
        \"messageId\": \"msg-003\",
        \"contextId\": \"$CTX\"
      }
    }
  }")
echo -e "${GREEN}第三轮响应:${NC} $(echo "$RESP3" | jq -r '.result.parts[0].text')"

# 4. 文件上传
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}📁 测试 4: 文件上传${NC}"
echo -e "${BLUE}========================================${NC}"

# 创建测试文件
echo "This is test content" > /tmp/test_file.txt
FILE_BYTES=$(base64 -w 0 /tmp/test_file.txt)

curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 4,
    \"method\": \"message/send\",
    \"params\": {
      \"message\": {
        \"role\": \"user\",
        \"parts\": [
          {\"kind\": \"text\", \"text\": \"请处理这个文件\"},
          {
            \"kind\": \"file\",
            \"file\": {
              \"name\": \"test_file.txt\",
              \"mimeType\": \"text/plain\",
              \"bytes\": \"$FILE_BYTES\"
            }
          }
        ],
        \"messageId\": \"msg-004\"
      }
    }
  }" | jq '.result.parts[0].text'

rm -f /tmp/test_file.txt

# 5. 结构化数据
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}📊 测试 5: 发送结构化数据${NC}"
echo -e "${BLUE}========================================${NC}"

curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {"kind": "text", "text": "处理这个数据"},
          {
            "kind": "data",
            "data": {
              "type": "order",
              "items": [
                {"name": "商品A", "quantity": 2, "price": 100},
                {"name": "商品B", "quantity": 1, "price": 200}
              ],
              "total": 400
            }
          }
        ],
        "messageId": "msg-005"
      }
    }
  }' | jq '.result'

# 6. SSE 流式响应
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}🌊 测试 6: SSE 流式响应${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}发送流式请求...${NC}"

curl -s -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 6,
    "method": "message/stream",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "写一段话"}],
        "messageId": "msg-006"
      }
    }
  }' | while IFS= read -r line; do
  if [[ "$line" == data:* ]]; then
    json="${line#data: }"
    kind=$(echo "$json" | jq -r '.result.kind // empty' 2>/dev/null || echo "")
    if [[ "$kind" == "artifact-update" ]]; then
      text=$(echo "$json" | jq -r '.result.artifact.parts[0].text // empty' 2>/dev/null || echo "")
      if [[ -n "$text" ]]; then
        echo -n "$text"
      fi
    elif [[ "$kind" == "status-update" ]]; then
      state=$(echo "$json" | jq -r '.result.status.state' 2>/dev/null || echo "")
      echo -e "\n${GREEN}状态: $state${NC}"
    fi
  fi
done

# 7. 完整 HTTP 抓包
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}📡 测试 7: 完整 HTTP 抓包${NC}"
echo -e "${BLUE}========================================${NC}"

curl -v -X POST "$SERVER/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 7,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "抓包测试"}],
        "messageId": "msg-007"
      }
    }
  }' 2>&1 | grep -E "^(<|>|{)" | head -20

# 完成
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 所有测试完成！${NC}"
echo -e "${GREEN}========================================${NC}"
