#!/usr/bin/env python3
"""
A2A 完整测试客户端
支持所有测试场景

运行: python3 test_client.py --help
"""

import argparse
import json
import time
import requests
import base64
from typing import Dict, Any, Optional, List

class A2ATestClient:
    """A2A 测试客户端"""
    
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.request_id = 0
    
    def _headers(self) -> dict:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    def _request(self, method: str, params: dict = None) -> dict:
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        resp = requests.post(
            self.base_url,
            json=payload,
            headers=self._headers(),
            timeout=30
        )
        
        return {
            "http_status": resp.status_code,
            "body": resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else resp.text
        }
    
    # ==================== 测试场景 ====================
    
    def test_agent_card(self) -> dict:
        """测试获取 Agent Card"""
        print("\n📋 测试 Agent Card...")
        
        resp = requests.get(
            f"{self.base_url}/.well-known/agent.json",
            headers=self._headers(),
            timeout=10
        )
        
        result = {
            "test": "agent_card",
            "status": "PASS" if resp.status_code == 200 else "FAIL",
            "http_status": resp.status_code,
            "body": resp.json() if resp.status_code == 200 else resp.text
        }
        
        print(f"  HTTP {resp.status_code}: {'✅' if resp.status_code == 200 else '❌'}")
        return result
    
    def test_simple_message(self, text: str = "Hello") -> dict:
        """测试简单消息"""
        print(f"\n💬 测试简单消息: '{text}'...")
        
        resp = self._request("message/send", {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": f"test-{time.time()}"
            }
        })
        
        success = resp['http_status'] == 200 and 'result' in resp.get('body', {})
        result = {
            "test": "simple_message",
            "status": "PASS" if success else "FAIL",
            "response": resp
        }
        
        print(f"  {'✅' if success else '❌'} {resp['http_status']}")
        return result
    
    def test_multi_turn(self, messages: List[str]) -> dict:
        """测试多轮对话"""
        print(f"\n🔄 测试多轮对话 ({len(messages)} 轮)...")
        
        context_id = None
        results = []
        
        for i, text in enumerate(messages):
            params = {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                    "messageId": f"msg-{i}"
                }
            }
            
            if context_id:
                params["message"]["contextId"] = context_id
            
            resp = self._request("message/send", params)
            
            if 'result' in resp.get('body', {}):
                context_id = resp['body']['result'].get('contextId')
                response_text = resp['body']['result'].get('parts', [{}])[0].get('text', '')
                print(f"  第{i+1}轮: {response_text[:50]}...")
                results.append({"round": i+1, "response": response_text[:100]})
        
        success = len(results) == len(messages)
        return {
            "test": "multi_turn",
            "status": "PASS" if success else "FAIL",
            "context_id": context_id,
            "results": results
        }
    
    def test_file_upload(self, file_path: str) -> dict:
        """测试文件上传"""
        print(f"\n📁 测试文件上传: {file_path}...")
        
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode()
        
        import os
        filename = os.path.basename(file_path)
        
        resp = self._request("message/send", {
            "message": {
                "role": "user",
                "parts": [
                    {"kind": "text", "text": "Process this file"},
                    {
                        "kind": "file",
                        "file": {
                            "name": filename,
                            "bytes": content
                        }
                    }
                ],
                "messageId": f"file-{time.time()}"
            }
        })
        
        success = resp['http_status'] == 200
        return {
            "test": "file_upload",
            "status": "PASS" if success else "FAIL",
            "filename": filename,
            "response": resp
        }
    
    def test_error_invalid_json(self) -> dict:
        """测试无效 JSON"""
        print("\n❌ 测试无效 JSON...")
        
        resp = requests.post(
            self.base_url,
            data="not valid json",
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        body = resp.json() if resp.headers.get('Content-Type', '').startswith('application/json') else resp.text
        success = resp.status_code >= 400 or (isinstance(body, dict) and 'error' in body)
        
        print(f"  {'✅' if success else '❌'} HTTP {resp.status_code}")
        return {
            "test": "invalid_json",
            "status": "PASS" if success else "FAIL",
            "http_status": resp.status_code
        }
    
    def test_error_missing_field(self) -> dict:
        """测试缺失必填字段"""
        print("\n❌ 测试缺失字段...")
        
        resp = self._request("message/send", {
            "message": {
                "role": "user",
                # 缺少 parts
                "messageId": "test"
            }
        })
        
        has_error = 'error' in resp.get('body', {})
        print(f"  {'✅' if has_error else '❌'} 返回错误")
        return {
            "test": "missing_field",
            "status": "PASS" if has_error else "FAIL"
        }
    
    def test_error_empty_parts(self) -> dict:
        """测试空 parts"""
        print("\n❌ 测试空 parts...")
        
        resp = self._request("message/send", {
            "message": {
                "role": "user",
                "parts": [],
                "messageId": "test"
            }
        })
        
        has_error = 'error' in resp.get('body', {})
        print(f"  {'✅' if has_error else '❌'} 返回错误")
        return {
            "test": "empty_parts",
            "status": "PASS" if has_error else "FAIL"
        }
    
    def run_all_tests(self) -> dict:
        """运行所有测试"""
        print("=" * 60)
        print("🧪 A2A 完整测试套件")
        print("=" * 60)
        
        results = []
        
        # 正常场景
        results.append(self.test_agent_card())
        results.append(self.test_simple_message())
        results.append(self.test_multi_turn(["Hello", "How are you?", "Goodbye"]))
        
        # 异常场景
        results.append(self.test_error_invalid_json())
        results.append(self.test_error_missing_field())
        results.append(self.test_error_empty_parts())
        
        # 统计
        passed = sum(1 for r in results if r['status'] == 'PASS')
        total = len(results)
        
        print("\n" + "=" * 60)
        print(f"测试结果: {passed}/{total} 通过")
        print("=" * 60)
        
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "results": results
        }

# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(description='A2A 测试客户端')
    parser.add_argument('url', help='Agent URL (e.g., http://127.0.0.1:8888)')
    parser.add_argument('--key', help='API Key')
    parser.add_argument('--test', choices=['all', 'card', 'message', 'multi', 'errors'],
                       default='all', help='测试类型')
    parser.add_argument('--text', default='Hello', help='测试消息文本')
    parser.add_argument('--file', help='测试文件上传')
    
    args = parser.parse_args()
    
    client = A2ATestClient(args.url, args.key)
    
    if args.test == 'all':
        result = client.run_all_tests()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.test == 'card':
        print(json.dumps(client.test_agent_card(), indent=2))
    elif args.test == 'message':
        print(json.dumps(client.test_simple_message(args.text), indent=2))
    elif args.test == 'multi':
        print(json.dumps(client.test_multi_turn(["Hello", "Hi", "Bye"]), indent=2))
    elif args.test == 'errors':
        results = [
            client.test_error_invalid_json(),
            client.test_error_missing_field(),
            client.test_error_empty_parts()
        ]
        print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
