import json
import os
import time
from typing import Any, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROVIDER = (os.getenv("LLM_PROVIDER") or "").strip().lower()
EMBEDDING_PROVIDER = (os.getenv("EMBEDDING_PROVIDER") or "").strip().lower()

QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_CHAT_MODEL = os.getenv("QWEN_CHAT_MODEL", "qwen-plus")
QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
DEEPSEEK_EMBEDDING_MODEL = os.getenv("DEEPSEEK_EMBEDDING_MODEL", "")

_embedding_dimensions_raw = os.getenv("QWEN_EMBEDDING_DIMENSIONS", "1024").strip()
EMBEDDING_DIMENSIONS: Optional[int]
if _embedding_dimensions_raw:
    try:
        EMBEDDING_DIMENSIONS = int(_embedding_dimensions_raw)
    except ValueError:
        EMBEDDING_DIMENSIONS = None
else:
    EMBEDDING_DIMENSIONS = None


def _resolve_provider() -> str:
    if PROVIDER in {"qwen", "dashscope"}:
        return "qwen"
    if PROVIDER == "deepseek":
        return "deepseek"
    if DEEPSEEK_API_KEY:
        return "deepseek"
    return "qwen"


ACTIVE_PROVIDER = _resolve_provider()


def _resolve_embedding_provider() -> str:
    if EMBEDDING_PROVIDER in {"qwen", "dashscope"}:
        return "qwen"
    if EMBEDDING_PROVIDER == "deepseek":
        return "deepseek"
    if QWEN_API_KEY and QWEN_EMBEDDING_MODEL:
        return "qwen"
    if DEEPSEEK_API_KEY and DEEPSEEK_EMBEDDING_MODEL:
        return "deepseek"
    return ACTIVE_PROVIDER


ACTIVE_EMBEDDING_PROVIDER = _resolve_embedding_provider()

if ACTIVE_PROVIDER == "deepseek":
    ACTIVE_API_KEY = DEEPSEEK_API_KEY
    ACTIVE_BASE_URL = DEEPSEEK_BASE_URL
    ACTIVE_CHAT_MODEL = DEEPSEEK_CHAT_MODEL
else:
    ACTIVE_API_KEY = QWEN_API_KEY
    ACTIVE_BASE_URL = QWEN_BASE_URL
    ACTIVE_CHAT_MODEL = QWEN_CHAT_MODEL

if ACTIVE_EMBEDDING_PROVIDER == "deepseek":
    ACTIVE_EMBEDDING_API_KEY = DEEPSEEK_API_KEY
    ACTIVE_EMBEDDING_BASE_URL = DEEPSEEK_BASE_URL
    ACTIVE_EMBEDDING_MODEL = DEEPSEEK_EMBEDDING_MODEL
else:
    ACTIVE_EMBEDDING_API_KEY = QWEN_API_KEY
    ACTIVE_EMBEDDING_BASE_URL = QWEN_BASE_URL
    ACTIVE_EMBEDDING_MODEL = QWEN_EMBEDDING_MODEL

if not ACTIVE_API_KEY:
    print(f"Warning: {ACTIVE_PROVIDER} API key is not configured.")
else:
    print(f"LLM provider: {ACTIVE_PROVIDER}, model: {ACTIVE_CHAT_MODEL}")

if ACTIVE_EMBEDDING_API_KEY and ACTIVE_EMBEDDING_MODEL:
    print(
        f"Embedding provider: {ACTIVE_EMBEDDING_PROVIDER}, "
        f"model: {ACTIVE_EMBEDDING_MODEL}"
    )
else:
    print(f"Warning: {ACTIVE_EMBEDDING_PROVIDER} embedding is not fully configured.")

client = OpenAI(
    api_key=ACTIVE_API_KEY or "missing-api-key",
    base_url=ACTIVE_BASE_URL,
)

embedding_client = OpenAI(
    api_key=ACTIVE_EMBEDDING_API_KEY or "missing-api-key",
    base_url=ACTIVE_EMBEDDING_BASE_URL,
)


CASE_COMPLETION_PROVIDER = (os.getenv("CASE_COMPLETION_PROVIDER") or "deepseek").strip().lower()
CASE_COMPLETION_MODEL = (os.getenv("CASE_COMPLETION_MODEL") or DEEPSEEK_CHAT_MODEL).strip()


def _resolve_case_completion_binding() -> tuple[str, str, str]:
    if CASE_COMPLETION_PROVIDER == "deepseek" and DEEPSEEK_API_KEY:
        return DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, CASE_COMPLETION_MODEL or DEEPSEEK_CHAT_MODEL
    return ACTIVE_API_KEY, ACTIVE_BASE_URL, ACTIVE_CHAT_MODEL


CASE_COMPLETION_API_KEY, CASE_COMPLETION_BASE_URL, CASE_COMPLETION_ACTIVE_MODEL = _resolve_case_completion_binding()
CASE_COMPLETION_ACTIVE_PROVIDER = (
    "deepseek" if CASE_COMPLETION_PROVIDER == "deepseek" and DEEPSEEK_API_KEY else ACTIVE_PROVIDER
)

case_completion_client = OpenAI(
    api_key=CASE_COMPLETION_API_KEY or "missing-api-key",
    base_url=CASE_COMPLETION_BASE_URL,
)


def get_chat_model() -> str:
    return ACTIVE_CHAT_MODEL


def get_case_completion_model() -> str:
    return CASE_COMPLETION_ACTIVE_MODEL


def get_case_completion_provider() -> str:
    return CASE_COMPLETION_ACTIVE_PROVIDER


def get_embedding_model() -> str:
    return ACTIVE_EMBEDDING_MODEL


def get_embedding_provider() -> str:
    return ACTIVE_EMBEDDING_PROVIDER


def get_embedding_dimensions() -> Optional[int]:
    return EMBEDDING_DIMENSIONS


def extract_message_text(response: Any) -> str:
    try:
        message = response.choices[0].message
    except Exception:
        return ""

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
            else:
                text = getattr(item, "text", "") or getattr(item, "content", "")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content or "")


def extract_json_payload(text: Any) -> Any:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            pass

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            pass
    return None


def create_json_chat_completion(
    *,
    messages: List[dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    extra_kwargs: Optional[dict[str, Any]] = None,
    llm_client: Optional[OpenAI] = None,
):
    request_messages = list(messages)
    request_messages.insert(
        0,
        {
            "role": "system",
            "content": (
                "Return valid json only. Do not output markdown, explanations, or whitespace padding. "
                "The response must be a single compact json object."
            ),
        },
    )

    kwargs: dict[str, Any] = {
        "model": model or get_chat_model(),
        "messages": request_messages,
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra_kwargs:
        kwargs.update(extra_kwargs)

    retries = 4 if ACTIVE_PROVIDER == "deepseek" else 2
    last_response = None
    for attempt in range(retries):
        if attempt > 0 and ACTIVE_PROVIDER == "deepseek":
            kwargs["temperature"] = min(1.0, float(kwargs.get("temperature", temperature)) + 0.05)

        active_client = llm_client or client
        response = active_client.chat.completions.create(**kwargs)
        last_response = response
        content = extract_message_text(response)
        if content and content.strip():
            return response

        finish_reason = ""
        try:
            finish_reason = str(response.choices[0].finish_reason or "")
        except Exception:
            finish_reason = ""

        provider_label = CASE_COMPLETION_ACTIVE_PROVIDER if llm_client is case_completion_client else ACTIVE_PROVIDER
        print(
            f"LLM empty JSON response detected: provider={provider_label}, "
            f"attempt={attempt + 1}, finish_reason={finish_reason or 'unknown'}"
        )

        kwargs["messages"] = list(request_messages) + [
            {
                "role": "system",
                "content": (
                    "Your previous reply was empty. Reply now with a non-empty compact json object only. "
                    "Do not emit spaces or blank lines."
                ),
            }
        ]
        time.sleep(0.35 * (attempt + 1))

    if ACTIVE_PROVIDER == "deepseek":
        fallback_kwargs = {
            "model": model or get_chat_model(),
            "messages": list(request_messages)
            + [
                {
                    "role": "system",
                    "content": (
                        "JSON mode was not usable. Reply with a non-empty plain text response whose entire body "
                        "is a single valid compact json object."
                    ),
                }
            ],
            "temperature": min(0.6, temperature),
            "max_tokens": max_tokens,
        }
        if extra_kwargs:
            for key, value in extra_kwargs.items():
                if key != "response_format":
                    fallback_kwargs[key] = value
        active_client = llm_client or client
        response = active_client.chat.completions.create(**fallback_kwargs)
        content = extract_message_text(response)
        if content and content.strip():
            print("LLM JSON fallback succeeded with plain-text JSON mode.")
            return response

    if last_response is not None:
        return last_response
    active_client = llm_client or client
    return active_client.chat.completions.create(**kwargs)


def create_case_completion_chat_completion(
    *,
    messages: List[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 6000,
    extra_kwargs: Optional[dict[str, Any]] = None,
):
    return create_json_chat_completion(
        messages=messages,
        model=get_case_completion_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        extra_kwargs=extra_kwargs,
        llm_client=case_completion_client,
    )


def create_embeddings(texts: List[str]) -> List[List[float]]:
    model = get_embedding_model()
    if not model:
        raise RuntimeError(f"{ACTIVE_EMBEDDING_PROVIDER} embedding model is not configured.")
    if not ACTIVE_EMBEDDING_API_KEY:
        raise RuntimeError(f"{ACTIVE_EMBEDDING_PROVIDER} embedding API key is not configured.")

    kwargs = {
        "model": model,
        "input": texts,
        "encoding_format": "float",
    }
    dimensions = get_embedding_dimensions()
    if dimensions and ACTIVE_EMBEDDING_PROVIDER == "qwen":
        kwargs["dimensions"] = dimensions

    response = embedding_client.embeddings.create(**kwargs)
    return [item.embedding for item in response.data]
