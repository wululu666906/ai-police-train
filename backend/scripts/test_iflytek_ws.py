"""尝试与科大讯飞听写 WebSocket 握手，验证密钥是否有效。"""
import json
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from services import iflytek_iat_service  # noqa: E402

try:
    import websocket
except ImportError:
    print("请安装 websocket-client: pip install websocket-client")
    raise SystemExit(3)


def main() -> int:
    url = iflytek_iat_service.build_iat_ws_url()
    app_id = iflytek_iat_service.IFLYTEK_APP_ID
    result: dict = {"opened": False, "error": None, "first_message": None}

    def on_open(ws):
        result["opened"] = True
        payload = {
            "common": {"app_id": app_id},
            "business": {"language": "zh_cn", "domain": "iat", "accent": "mandarin"},
            "data": {"status": 2},
        }
        ws.send(json.dumps(payload))

    def on_message(ws, message):
        result["first_message"] = message
        ws.close()

    def on_error(ws, error):
        result["error"] = str(error)

    ws_app = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message, on_error=on_error)
    ws_app.run_forever(ping_interval=20, ping_timeout=10)

    print("=== WebSocket 握手测试 ===")
    print("opened:", result["opened"])
    if result["error"]:
        print("error:", result["error"])
        return 2
    if result["first_message"]:
        data = json.loads(result["first_message"])
        print("response:", data)
        if data.get("code") == 0:
            print("\n结果: 科大讯飞鉴权通过")
            return 0
        print("\n结果: 已连接但业务返回错误 —", data.get("message"))
        return 1
    print("\n结果: 连接异常，未收到响应")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
