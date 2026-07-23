import os
import socket
from typing import Any
from urllib.parse import urlparse

from openai import OpenAI

from env_loader import load_backend_env
from services.qwen_config import (
    qwen_api_key,
    qwen_default_headers,
    resolve_qwen_base_url,
    resolve_qwen_realtime_url,
)

load_backend_env()

QWEN_ASR_API_KEY = qwen_api_key()


def get_qwen_asr_api_key() -> str:
    return qwen_api_key()


def get_qwen_asr_base_url() -> str:
    return resolve_qwen_base_url("QWEN_ASR_BASE_URL")


def get_qwen_asr_model() -> str:
    return os.getenv("QWEN_ASR_MODEL", "qwen3-asr-flash")


def get_qwen_realtime_asr_url() -> str:
    return resolve_qwen_realtime_url("QWEN_REALTIME_ASR_URL")


def get_qwen_realtime_asr_model() -> str:
    return os.getenv("QWEN_REALTIME_ASR_MODEL", "qwen3-asr-flash-realtime")


def _is_disabled(value: str) -> bool:
    return value.strip().lower() in {"0", "false", "off", "disabled", "none", "direct"}


def _local_proxy_url_for_realtime(url: str) -> str | None:
    configured = os.getenv("QWEN_REALTIME_ASR_PROXY", "").strip()
    if configured:
        return None if _is_disabled(configured) else configured
    if _is_disabled(os.getenv("QWEN_REALTIME_ASR_PROXY_AUTO", "1")):
        return None

    host = urlparse(url).hostname or ""
    if not host:
        return None
    try:
        addresses = [item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
    except OSError:
        return None

    # 198.18.0.0/15 is commonly used by local proxy fake-ip DNS. Direct sockets
    # to these addresses fail unless the process uses the local proxy port.
    if not any(address.startswith(("198.18.", "198.19.")) for address in addresses):
        return None

    for port in (7897, 7890, 7891, 1080, 10809):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return f"http://127.0.0.1:{port}"
        except OSError:
            continue
    return None


def get_qwen_realtime_asr_proxy() -> str | None:
    return _local_proxy_url_for_realtime(get_qwen_realtime_asr_url())


def get_qwen_asr_max_data_url_bytes() -> int:
    try:
        return int(os.getenv("QWEN_ASR_MAX_DATA_URL_BYTES", str(10 * 1024 * 1024)))
    except ValueError:
        return 10 * 1024 * 1024


def create_qwen_asr_client() -> OpenAI:
    return OpenAI(
        api_key=get_qwen_asr_api_key() or "missing-api-key",
        base_url=get_qwen_asr_base_url(),
        default_headers=qwen_default_headers(get_qwen_asr_base_url()),
    )


class SpeechRecognitionError(RuntimeError):
    pass


def get_speech_status() -> dict[str, Any]:
    realtime_proxy = get_qwen_realtime_asr_proxy()
    return {
        "configured": bool(get_qwen_asr_api_key()),
        "provider": "qwen",
        "source": "admin_llm_config",
        "offline_model": get_qwen_asr_model(),
        "offline_base_url": get_qwen_asr_base_url(),
        "realtime_model": get_qwen_realtime_asr_model(),
        "realtime_url": get_qwen_realtime_asr_url(),
        "realtime_proxy": "backend",
        "realtime_proxy_mode": "auto_local_proxy" if realtime_proxy else "direct",
        "realtime_proxy_uses_system_proxy": False,
        "realtime_turn_detection": "server_vad",
    }


def build_realtime_url() -> str:
    realtime_url = get_qwen_realtime_asr_url()
    separator = "&" if "?" in realtime_url else "?"
    return f"{realtime_url}{separator}model={get_qwen_realtime_asr_model()}"


def build_realtime_session_update(*, language: str = "zh") -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "input_audio_format": "pcm",
            "sample_rate": 16000,
            "input_audio_transcription": {
                "model": get_qwen_realtime_asr_model(),
                "language": language,
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.30,
                "prefix_padding_ms": 800,
                "silence_duration_ms": 1600,
            },
        },
    }


def extract_realtime_transcript(event: dict[str, Any]) -> str:
    if event.get("type") != "conversation.item.input_audio_transcription.completed":
        return ""
    return str(event.get("transcript") or event.get("text") or "").strip()


def extract_realtime_transcript_delta(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")
    if event_type == "conversation.item.input_audio_transcription.delta":
        text = str(event.get("text") or "")
        stash = str(event.get("stash") or "")
        return f"{text}{stash}".strip() or str(event.get("delta") or "").strip()
    if event_type == "conversation.item.input_audio_transcription.text":
        return str(event.get("text") or "").strip()
    return ""


def _extract_annotations(message: Any) -> list[dict[str, Any]]:
    annotations = getattr(message, "annotations", None) or []
    if not isinstance(annotations, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in annotations:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append(
                {
                    key: getattr(item, key)
                    for key in ("type", "language", "emotion")
                    if getattr(item, key, None) is not None
                }
            )
    return normalized


def _extract_message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(getattr(item, "text", "") or getattr(item, "content", "")))
        return "".join(parts).strip()
    return str(content or "").strip()


def transcribe_audio_data_url(
    audio_data_url: str,
    *,
    language: str | None = None,
    enable_itn: bool = True,
) -> dict[str, Any]:
    data_url = str(audio_data_url or "").strip()
    if not data_url.startswith("data:audio/") or ";base64," not in data_url:
        raise SpeechRecognitionError("请上传浏览器录制的音频数据")
    if len(data_url.encode("utf-8")) > get_qwen_asr_max_data_url_bytes():
        raise SpeechRecognitionError("语音片段过长，请控制在 3 分钟以内")
    if not get_qwen_asr_api_key():
        raise SpeechRecognitionError("未配置 QWEN_API_KEY，无法调用千问语音识别")

    asr_options: dict[str, Any] = {"enable_itn": enable_itn}
    if language:
        asr_options["language"] = language

    response = create_qwen_asr_client().chat.completions.create(
        model=get_qwen_asr_model(),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": data_url,
                        },
                    }
                ],
            }
        ],
        extra_body={"asr_options": asr_options},
    )
    message = response.choices[0].message
    text = _extract_message_text(message)
    annotations = _extract_annotations(message)
    audio_info = next((item for item in annotations if item.get("type") == "audio_info"), {})
    return {
        "text": text,
        "model": getattr(response, "model", get_qwen_asr_model()),
        "language": audio_info.get("language"),
        "emotion": audio_info.get("emotion"),
    }
