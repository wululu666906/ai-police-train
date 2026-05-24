"""检查科大讯飞听写配置是否完整，并尝试生成 WebSocket 鉴权 URL。"""
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from services import iflytek_iat_service  # noqa: E402


def main() -> int:
    config = iflytek_iat_service.get_iflytek_public_config()
    print("=== 科大讯飞配置检查 ===")
    print(config)

    if not config["configured"]:
        print("\n结果: 未就绪 — 还缺 APP_ID 或 API_SECRET（API_KEY 已写入）")
        return 1

    try:
        url = iflytek_iat_service.build_iat_ws_url()
        print("\n结果: 鉴权 URL 生成成功")
        print(url[:120] + "...")
        return 0
    except Exception as error:
        print(f"\n结果: 鉴权 URL 生成失败 — {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
