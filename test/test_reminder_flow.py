#!/usr/bin/env python3
"""提醒系统集成测试

测试流程:
  1. 模拟 APP 发送提醒命令到服务器 (HTTP API)
  2. 模拟设备连接 WebSocket 接收命令
  3. 验证设备收到 reminder 并正确响应

用法:
  python test_reminder_flow.py                    # 完整测试
  python test_reminder_flow.py --skip-ws          # 仅测试 HTTP API
  python test_reminder_flow.py --server 47.118.26.156:9099
"""

import json
import sys
import os
import time
import threading
import argparse
import requests


# 添加上级目录到 path，用于导入 simulation
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log(msg):
    print(f"[TEST][{time.strftime('%H:%M:%S')}] {msg}")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name):
        self.passed += 1
        log(f"  ✓ {name}")

    def fail(self, name, detail=""):
        self.failed += 1
        self.errors.append(f"{name}: {detail}")
        log(f"  ✗ {name} - {detail}")


def test_http_api(result, server_host, server_port):
    """测试 HTTP API：登录 + 发送提醒命令"""
    base = f"http://{server_host}:{server_port}/api/v1"

    # 1. 手机号登录
    log("=== HTTP: Login ===")
    try:
        r = requests.get(f"{base}/aipet/app/auth/13800138000/888888", timeout=10)
        data = r.json()
        if data.get("success"):
            token = data.get("data")
            result.ok("Login via phone")
        else:
            result.fail("Login", f"response: {data}")
            return None, None
    except Exception as e:
        result.fail("Login", str(e))
        return None, None

    # 2. 获取宠物列表
    log("=== HTTP: My Pets ===")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{base}/aipet/app/myaipets", headers=headers, timeout=10)
        data = r.json()
        if data.get("success") and data.get("data"):
            pets = data["data"]
            pet_id = pets[0].get("id") or pets[0].get("petId") if pets else None
            if pet_id:
                result.ok(f"Got pet list: {len(pets)} pets, first={pet_id}")
            else:
                result.fail("Pet list", "No pet found or invalid response")
                return token, None
        else:
            result.fail("Pet list", f"response: {data}")
            return token, None
    except Exception as e:
        result.fail("Pet list", str(e))
        return token, None

    # 3. 发送提醒命令
    log("=== HTTP: Send Reminder Command ===")
    try:
        reminder_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 60))
        payload = {
            "commandParams": {
                "reminder_data": {
                    "title": "集成测试提醒",
                    "content": "这是通过 HTTP API 发送的测试提醒",
                    "reminder_time": reminder_time,
                    "repeat_type": "",
                }
            }
        }
        r = requests.post(
            f"{base}/aipet/app/command/{pet_id}/reminder",
            headers=headers, json=payload, timeout=10
        )
        data = r.json()
        if data.get("success"):
            cmd_id = data.get("data", {}).get("commandId", "?")
            result.ok(f"Reminder command sent: id={cmd_id}")
        else:
            result.fail("Send reminder", f"response: {data}")
    except Exception as e:
        result.fail("Send reminder", str(e))

    return token, pet_id


def test_websocket(result, server_host, ws_port):
    """测试 WebSocket 设备连接"""
    import websocket

    log("=== WS: Device Connection ===")
    received_commands = []
    ws_url = f"ws://{server_host}:{ws_port}/openclaw-wwh/robot_websocket"

    def on_open(ws):
        log("WS connected, sending auth...")
        ws.send(json.dumps({"type": "auth", "access_token": "AIPET-TEST-001"}))

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            t = msg.get("type", "")
            if t == "auth":
                if msg.get("success"):
                    result.ok("WS Auth successful")
                else:
                    result.fail("WS Auth", msg.get("message", ""))
            elif t == "server_command":
                cmd = msg.get("command", "")
                cmd_id = msg.get("command_id", "")
                log(f"WS received command: {cmd} id={cmd_id}")
                received_commands.append(msg)
                # 回复 command_response
                resp = {
                    "type": "command_response",
                    "command_id": cmd_id,
                    "command": cmd,
                    "status": "success",
                    "result": {"msg": "test_ok"},
                }
                ws.send(json.dumps(resp))
                result.ok(f"WS handled command: {cmd}")
            elif t == "heartbeat":
                pass  # 心跳正常
            elif t == "chat":
                log(f"WS chat: {msg.get('content','')}")
        except Exception as e:
            log(f"WS message error: {e}")

    def on_error(ws, error):
        log(f"WS error: {error}")

    def on_close(ws, status, msg):
        log(f"WS closed: {status}")

    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message,
                                 on_error=on_error, on_close=on_close)
    wst = threading.Thread(target=ws.run_forever, daemon=True)
    wst.start()

    # 等待 15 秒接收命令
    time.sleep(15)

    ws.close()
    return received_commands


def main():
    parser = argparse.ArgumentParser(description="Reminder System Integration Test")
    parser.add_argument("--server", default="47.118.26.156", help="服务器 HTTP 地址")
    parser.add_argument("--http-port", type=int, default=9099, help="HTTP 端口")
    parser.add_argument("--ws-port", type=int, default=3000, help="WebSocket 端口")
    parser.add_argument("--skip-ws", action="store_true", help="跳过 WebSocket 测试")
    args = parser.parse_args()

    result = TestResult()

    log("=" * 50)
    log("Reminder System Integration Test")
    log(f"Server HTTP: {args.server}:{args.http_port}")
    log(f"Server WS:   {args.server}:{args.ws_port}")
    log("=" * 50)

    # 1. HTTP API 测试
    log("\n[Phase 1] HTTP API Test")
    token, pet_id = test_http_api(result, args.server, args.http_port)

    # 2. WebSocket 测试
    if not args.skip_ws:
        log("\n[Phase 2] WebSocket Device Test")
        test_websocket(result, args.server, args.ws_port)
    else:
        log("\n[Phase 2] Skipped (--skip-ws)")

    # 3. 结果
    log("\n" + "=" * 50)
    log(f"Results: {result.passed} passed, {result.failed} failed")
    if result.errors:
        log("Errors:")
        for e in result.errors:
            log(f"  - {e}")

    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

