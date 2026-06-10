"""更新 Claude 配置 — 从环境变量读取 API key 和 base URL"""
import json
import os
import sys

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")

if not ANTHROPIC_API_KEY:
    print("❌ 请设置环境变量 ANTHROPIC_API_KEY", file=sys.stderr)
    sys.exit(1)

path = "/home/oy0/.claude.json"
with open(path) as f:
    config = json.load(f)

config.setdefault("env", {})
config["env"]["ANTHROPIC_BASE_URL"] = ANTHROPIC_BASE_URL or ""
config["env"]["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

with open(path, "w") as f:
    json.dump(config, f, indent=2)

print("✅ Claude 配置已更新")
print(f"   BASE_URL: {config['env']['ANTHROPIC_BASE_URL']}")
print(f"   API_KEY: {config['env']['ANTHROPIC_API_KEY'][:8]}...")
