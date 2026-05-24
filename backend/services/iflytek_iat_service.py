import base64
import hashlib
import hmac
import os
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urlencode

IFLYTEK_IAT_HOST = os.getenv("IFLYTEK_IAT_HOST", "iat-api.xfyun.cn")
IFLYTEK_IAT_PATH = os.getenv("IFLYTEK_IAT_PATH", "/v2/iat")
IFLYTEK_APP_ID = os.getenv("IFLYTEK_APP_ID", "").strip()
IFLYTEK_API_KEY = os.getenv("IFLYTEK_API_KEY", "").strip()
IFLYTEK_API_SECRET = os.getenv("IFLYTEK_API_SECRET", "").strip()


def is_iflytek_configured() -> bool:
    return bool(IFLYTEK_APP_ID and IFLYTEK_API_KEY and IFLYTEK_API_SECRET)


def get_iflytek_public_config() -> dict:
    return {
        "configured": is_iflytek_configured(),
        "app_id": IFLYTEK_APP_ID if is_iflytek_configured() else "",
        "host": IFLYTEK_IAT_HOST,
        "path": IFLYTEK_IAT_PATH,
        "has_api_key": bool(IFLYTEK_API_KEY),
        "has_api_secret": bool(IFLYTEK_API_SECRET),
    }


def build_iat_ws_url() -> str:
    if not is_iflytek_configured():
        missing = []
        if not IFLYTEK_APP_ID:
            missing.append("IFLYTEK_APP_ID")
        if not IFLYTEK_API_KEY:
            missing.append("IFLYTEK_API_KEY")
        if not IFLYTEK_API_SECRET:
            missing.append("IFLYTEK_API_SECRET")
        raise ValueError(f"科大讯飞配置不完整，缺少: {', '.join(missing)}")

    host = IFLYTEK_IAT_HOST
    path = IFLYTEK_IAT_PATH
    date = format_datetime(datetime.now(timezone.utc), usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        IFLYTEK_API_SECRET.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{IFLYTEK_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": host})
    return f"wss://{host}{path}?{query}"
