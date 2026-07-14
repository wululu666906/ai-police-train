import os
from typing import Any

from openai import OpenAI

from env_loader import load_backend_env

load_backend_env()

QWEN_ASR_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY", "")
QWEN_ASR_BASE_URL = os.getenv("QWEN_ASR_BASE_URL") or os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
QWEN_ASR_MODEL = os.getenv("QWEN_ASR_MODEL", "qwen3-asr-flash")
QWEN_REALTIME_ASR_URL = os.getenv(
    "QWEN_REALTIME_ASR_URL",
    "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
)
QWEN_REALTIME_ASR_MODEL = os.getenv("QWEN_REALTIME_ASR_MODEL", "qwen3-asr-flash-realtime")
QWEN_ASR_MAX_DATA_URL_BYTES = int(os.getenv("QWEN_ASR_MAX_DATA_URL_BYTES", str(10 * 1024 * 1024)))

_client = OpenAI(
    api_key=QWEN_ASR_API_KEY or "missing-api-key",
    base_url=QWEN_ASR_BASE_URL,
)


class SpeechRecognitionError(RuntimeError):
    pass


def get_speech_status() -> dict[str, Any]:
    return {
        "configured": bool(QWEN_ASR_API_KEY),
        "offline_model": QWEN_ASR_MODEL,
        "realtime_model": QWEN_REALTIME_ASR_MODEL,
        "realtime_url": QWEN_REALTIME_ASR_URL,
        "realtime_turn_detection": "server_vad",
    }


def build_realtime_url() -> str:
    separator = "&" if "?" in QWEN_REALTIME_ASR_URL else "?"
    return f"{QWEN_REALTIME_ASR_URL}{separator}model={QWEN_REALTIME_ASR_MODEL}"


def build_realtime_session_update(*, language: str = "zh") -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "input_audio_format": "pcm",
            "sample_rate": 16000,
            "input_audio_transcription": {
                "model": QWEN_REALTIME_ASR_MODEL,
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
    if len(data_url.encode("utf-8")) > QWEN_ASR_MAX_DATA_URL_BYTES:
        raise SpeechRecognitionError("语音片段过长，请控制在 3 分钟以内")
    if not QWEN_ASR_API_KEY:
        raise SpeechRecognitionError("未配置 DASHSCOPE_API_KEY，无法调用千问语音识别")

    asr_options: dict[str, Any] = {"enable_itn": enable_itn}
    if language:
        asr_options["language"] = language

    response = _client.chat.completions.create(
        model=QWEN_ASR_MODEL,
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
        "model": getattr(response, "model", QWEN_ASR_MODEL),
        "language": audio_info.get("language"),
        "emotion": audio_info.get("emotion"),
    }
