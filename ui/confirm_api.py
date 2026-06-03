"""
⚠️ 废弃模块 — 此文件为早期原型，已不再维护。

确认 API 功能已整合到 Streamlit UI 中（ui/pages_confirm.py）。
此文件依赖未声明的 flask 包，且包含硬编码路径和变量遮蔽 bug。
如需 REST API 功能，请使用 Streamlit 内置的确认页面。
"""

# 以下代码保留供参考，不建议在生产环境使用。
# 已知问题：
#   1. 依赖 flask（未声明在 pyproject.toml 中）
#   2. 硬编码路径 /home/oy0/security-agent
#   3. 监听 0.0.0.0 存在安全风险
#   4. 变量名 request 遮蔽了 flask.request

import sys
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from flask import Flask, request as flask_request, jsonify
except ImportError:
    print("⚠️ 需要安装 flask: pip install flask")
    sys.exit(1)

from security_agent.confirm import get_confirmation_manager


app = Flask(__name__)
manager = get_confirmation_manager()


@app.route('/api/confirmations', methods=['GET'])
def get_confirmations():
    """获取所有确认请求"""
    pending = manager.list_pending_requests()
    return jsonify({
        "pending": [req.to_dict() for req in pending],
        "count": len(pending)
    })


@app.route('/api/confirmations/<request_id>', methods=['GET'])
def get_confirmation(request_id):
    """获取单个确认请求"""
    req = manager.get_request(request_id)
    if req:
        return jsonify(req.to_dict())
    return jsonify({"error": "Request not found"}), 404


@app.route('/api/confirmations/<request_id>/approve', methods=['POST'])
def approve_confirmation(request_id):
    """批准确认请求"""
    data = flask_request.get_json() or {}
    reason = data.get('reason', '')
    responder = data.get('responder', 'user')
    success = manager.approve_request(request_id, responder, reason)
    if success:
        return jsonify({"status": "approved", "request_id": request_id})
    return jsonify({"error": "Failed to approve"}), 400


@app.route('/api/confirmations/<request_id>/reject', methods=['POST'])
def reject_confirmation(request_id):
    """拒绝确认请求"""
    data = flask_request.get_json() or {}
    reason = data.get('reason', '')
    responder = data.get('responder', 'user')
    success = manager.reject_request(request_id, responder, reason)
    if success:
        return jsonify({"status": "rejected", "request_id": request_id})
    return jsonify({"error": "Failed to reject"}), 400


@app.route('/api/confirmations/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    stats = manager.get_stats()
    return jsonify(stats)


if __name__ == '__main__':
    print("⚠️ 此为废弃模块，建议使用 Streamlit 确认页面")
    app.run(host='127.0.0.1', port=5001, debug=True)