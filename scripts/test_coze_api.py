#!/usr/bin/env python3
"""Coze API 连通性测试脚本 (coze.cn)"""
import os, sys, json
import httpx

COZE_API_TOKEN = os.getenv("COZE_API_TOKEN", "YOUR_TOKEN")
COZE_BOT_ID = os.getenv("COZE_BOT_ID", "YOUR_BOT_ID")
BASE = "https://api.coze.cn"

if "YOUR_" in COZE_API_TOKEN or "YOUR_" in COZE_BOT_ID:
    print("请先设置环境变量:")
    print("  export COZE_API_TOKEN='pat_xxxx'")
    print("  export COZE_BOT_ID='xxxxxxx'")
    sys.exit(1)

headers = {"Authorization": f"Bearer {COZE_API_TOKEN}", "Content-Type": "application/json"}

print("=== 测试 Bot 信息 ===")
try:
    r = httpx.get(f"{BASE}/v1/bots/{COZE_BOT_ID}", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))
except Exception as e:
    print(f"异常: {e}")

print("\n=== 测试 Chat API ===")
try:
    payload = {"bot_id": COZE_BOT_ID, "user": "test-user", "query": "你好", "stream": False}
    r = httpx.post(f"{BASE}/v1/chat", headers=headers, json=payload, timeout=30)
    print(f"HTTP {r.status_code}")
    data = r.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if data.get("code") == 0:
        print("\n✅ Coze API 调用成功!")
    else:
        print(f"\n❌ 错误: {data.get('msg')}")
except Exception as e:
    print(f"异常: {e}")