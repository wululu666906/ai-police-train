import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, List, Optional

from openai import OpenAI

from env_loader import load_backend_env

load_backend_env()

PROVIDER = (os.getenv("LLM_PROVIDER") or "").strip().lower()
EMBEDDING_PROVIDER = (os.getenv("EMBEDDING_PROVIDER") or "").strip().lower()

QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_CHAT_MODEL = os.getenv("QWEN_CHAT_MODEL", "qwen-plus")
QWEN_LONG_OUTPUT_MODEL = os.getenv("QWEN_LONG_OUTPUT_MODEL", QWEN_CHAT_MODEL)
QWEN_EMBEDDING_MODEL = os.getenv("QWEN_EMBEDDING_MODEL", "text-embedding-v4")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# DeepSeek routing: default AI jobs use the low-latency Flash model.  Case
# reconstruction/scene writing and role performance use Pro explicitly.
DEEPSEEK_CHAT_MODEL = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash")
DEEPSEEK_CASE_MODEL = os.getenv("DEEPSEEK_CASE_MODEL", "deepseek-v4-pro")
DEEPSEEK_ROLEPLAY_MODEL = os.getenv("DEEPSEEK_ROLEPLAY_MODEL", "deepseek-v4-pro")
DEEPSEEK_LONG_OUTPUT_MODEL = os.getenv("DEEPSEEK_LONG_OUTPUT_MODEL", DEEPSEEK_CHAT_MODEL)
DEEPSEEK_EMBEDDING_MODEL = os.getenv("DEEPSEEK_EMBEDDING_MODEL", "")
DEEPSEEK_REASONING_MODE = (os.getenv("DEEPSEEK_REASONING_MODE") or "disabled").strip().lower()

_embedding_dimensions_raw = os.getenv("QWEN_EMBEDDING_DIMENSIONS", "1024").strip()
EMBEDDING_DIMENSIONS: Optional[int]
if _embedding_dimensions_raw:
    try:
        EMBEDDING_DIMENSIONS = int(_embedding_dimensions_raw)
    except ValueError:
        EMBEDDING_DIMENSIONS = None
else:
    EMBEDDING_DIMENSIONS = None


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


LLM_TIMEOUT_SECONDS = _env_float("LLM_TIMEOUT_SECONDS", 300.0)
EMBEDDING_TIMEOUT_SECONDS = _env_float("EMBEDDING_TIMEOUT_SECONDS", LLM_TIMEOUT_SECONDS)
CASE_AI_MAX_TOKENS = _env_int("CASE_AI_MAX_TOKENS", 128000)
DEEPSEEK_MAX_OUTPUT_TOKENS = _env_int("DEEPSEEK_MAX_OUTPUT_TOKENS", CASE_AI_MAX_TOKENS)
QWEN_MAX_OUTPUT_TOKENS = _env_int("QWEN_MAX_OUTPUT_TOKENS", 32768)


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
    timeout=LLM_TIMEOUT_SECONDS,
)

embedding_client = OpenAI(
    api_key=ACTIVE_EMBEDDING_API_KEY or "missing-api-key",
    base_url=ACTIVE_EMBEDDING_BASE_URL,
    timeout=EMBEDDING_TIMEOUT_SECONDS,
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
    timeout=LLM_TIMEOUT_SECONDS,
)

qwen_chat_client = OpenAI(
    api_key=QWEN_API_KEY or "missing-api-key",
    base_url=QWEN_BASE_URL,
    timeout=LLM_TIMEOUT_SECONDS,
)

deepseek_chat_client = OpenAI(
    api_key=DEEPSEEK_API_KEY or "missing-api-key",
    base_url=DEEPSEEK_BASE_URL,
    timeout=LLM_TIMEOUT_SECONDS,
)


def _provider_for_client(llm_client: Optional[OpenAI]) -> str:
    if llm_client is case_completion_client:
        return CASE_COMPLETION_ACTIVE_PROVIDER
    if llm_client is qwen_chat_client:
        return "qwen"
    if llm_client is deepseek_chat_client:
        return "deepseek"
    return ACTIVE_PROVIDER


def _chat_client_for_provider(provider: str) -> OpenAI:
    if provider == "qwen":
        return qwen_chat_client
    if provider == "deepseek":
        return deepseek_chat_client
    return client


def _chat_model_for_provider(provider: str) -> str:
    if provider == "qwen":
        return QWEN_CHAT_MODEL
    if provider == "deepseek":
        return DEEPSEEK_CHAT_MODEL
    return ACTIVE_CHAT_MODEL


def get_chat_completion_binding(
    provider: str | None = None,
    model: str | None = None,
) -> tuple[OpenAI, str, str, str]:
    """Return a configured chat client without changing the process-wide default."""
    normalized = (provider or ACTIVE_PROVIDER).strip().lower()
    if normalized == "dashscope":
        normalized = "qwen"
    if normalized not in {"qwen", "deepseek"}:
        normalized = ACTIVE_PROVIDER

    api_key = QWEN_API_KEY if normalized == "qwen" else DEEPSEEK_API_KEY
    return (
        _chat_client_for_provider(normalized),
        (model or _chat_model_for_provider(normalized)).strip(),
        normalized,
        api_key,
    )


def get_long_output_model(provider: str | None = None) -> str:
    """Resolve the explicitly configured long-output model for case workflows."""
    resolved = provider or ACTIVE_PROVIDER
    if resolved == "qwen":
        return QWEN_LONG_OUTPUT_MODEL
    if resolved == "deepseek":
        return DEEPSEEK_LONG_OUTPUT_MODEL
    return ACTIVE_CHAT_MODEL


def get_case_workflow_model(provider: str | None = None) -> str:
    """Model for evidence extraction, case worldview and scene generation."""
    resolved = provider or ACTIVE_PROVIDER
    if resolved == "deepseek":
        return DEEPSEEK_CASE_MODEL
    return get_long_output_model(resolved)


def get_roleplay_model(provider: str | None = None) -> str:
    """Model for live simulated-role dialogue and cast direction."""
    resolved = provider or ACTIVE_PROVIDER
    if resolved == "deepseek":
        return DEEPSEEK_ROLEPLAY_MODEL
    return _chat_model_for_provider(resolved)


def get_fast_generation_kwargs(provider: str | None = None) -> dict[str, Any]:
    """Low-latency provider control; set mode=default when unsupported."""
    resolved = provider or ACTIVE_PROVIDER
    if resolved == "deepseek" and DEEPSEEK_REASONING_MODE in {"disabled", "off", "false", "0"}:
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}


def get_provider_max_output_tokens(provider: str | None = None) -> int:
    resolved = provider or ACTIVE_PROVIDER
    if resolved == "qwen":
        return QWEN_MAX_OUTPUT_TOKENS
    if resolved == "deepseek":
        return DEEPSEEK_MAX_OUTPUT_TOKENS
    return CASE_AI_MAX_TOKENS


def _provider_has_api_key(provider: str) -> bool:
    if provider == "qwen":
        return bool(QWEN_API_KEY)
    if provider == "deepseek":
        return bool(DEEPSEEK_API_KEY)
    return bool(ACTIVE_API_KEY)


def _provider_fallback_order(provider: str) -> list[str]:
    candidates = ["qwen", "deepseek"] if provider == "deepseek" else ["deepseek", "qwen"]
    return [item for item in candidates if item != provider and _provider_has_api_key(item)]


class LLMJsonCompletionError(RuntimeError):
    """Raised only after JSON mode, plain JSON mode, and provider failover fail."""

    def __init__(self, message: str, trace: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.trace = trace or []


def _llm_error_summary(exc: Exception) -> str:
    text = str(exc or "").strip()
    text = re.sub(r"sk-[A-Za-z0-9_.-]+", "sk-***", text)
    return text[:500] or exc.__class__.__name__


def get_chat_model() -> str:
    return ACTIVE_CHAT_MODEL


def _response_usage(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "output_tokens": getattr(usage, "completion_tokens", None) if usage else None,
    }


def _response_finish_reason(response: Any) -> str:
    try:
        return str(response.choices[0].finish_reason or "")
    except Exception:
        return ""


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

    raw = raw.strip("\ufeff")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw).strip()

    def _try_load(candidate: str) -> Any:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, str):
                nested = parsed.strip()
                if nested and nested != candidate:
                    return _try_load(nested)
            return parsed
        except Exception:
            repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
            if repaired != candidate:
                try:
                    return json.loads(repaired)
                except Exception:
                    pass
        return None

    parsed = _try_load(raw)
    if parsed is not None:
        return parsed

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = _try_load(raw[start : end + 1])
        if parsed is not None:
            return parsed

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        parsed = _try_load(raw[start : end + 1])
        if parsed is not None:
            return parsed
    return None


def create_json_chat_completion(
    *,
    messages: List[dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    extra_kwargs: Optional[dict[str, Any]] = None,
    llm_client: Optional[OpenAI] = None,
    retries: Optional[int] = None,
    allow_plain_json_fallback: bool = True,
    return_trace: bool = False,
    long_output: bool = False,
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
        "max_tokens": max(1, int(max_tokens)),
    }
    if extra_kwargs:
        kwargs.update(extra_kwargs)

    provider = _provider_for_client(llm_client)
    requested_max_tokens = max(1, int(max_tokens))
    kwargs["max_tokens"] = min(requested_max_tokens, get_provider_max_output_tokens(provider))
    trace: list[dict[str, Any]] = []

    def _attempt(
        *,
        attempt_provider: str,
        attempt_model: str,
        mode: str,
        ordinal: int,
        max_output_tokens: int,
        call,
    ):
        started_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        entry: dict[str, Any] = {
            "provider": attempt_provider,
            "model": attempt_model,
            "mode": mode,
            "attempt": ordinal,
            "max_tokens": max_output_tokens,
            "started_at": started_at.isoformat(),
        }
        try:
            response = call()
            content = extract_message_text(response)
            entry.update(
                {
                    "status": "success" if content and content.strip() else "empty",
                    "finish_reason": _response_finish_reason(response),
                    "response_chars": len(content or ""),
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                    **_response_usage(response),
                }
            )
            trace.append(entry)
            return response, content
        except Exception as exc:
            summary = _llm_error_summary(exc)
            entry.update({
                "status": "error",
                "error": summary,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })
            trace.append(entry)
            return None, ""

    def _success(response: Any, final_provider: str):
        result_trace = {
            "primary_provider": provider,
            "final_provider": final_provider,
            "failed_attempts": sum(1 for item in trace if item.get("status") != "success"),
            "switched_provider": final_provider != provider,
            "attempts": trace,
        }
        return (response, result_trace) if return_trace else response

    # DeepSeek may acknowledge JSON mode with finish_reason=stop but an empty
    # message. Retrying that identical request rarely changes the outcome; move
    # quickly to plain JSON mode and then to the configured alternate provider.
    resolved_retries = retries if retries is not None else (1 if provider == "deepseek" else 2)
    resolved_retries = max(1, int(resolved_retries))
    errors: list[str] = []
    primary_unavailable = False
    for attempt in range(resolved_retries):
        if attempt > 0 and provider == "deepseek":
            kwargs["temperature"] = min(1.0, float(kwargs.get("temperature", temperature)) + 0.05)

        active_client = llm_client or client
        response, content = _attempt(
            attempt_provider=provider,
            attempt_model=str(kwargs["model"]),
            mode="strict_json",
            ordinal=attempt + 1,
            max_output_tokens=int(kwargs["max_tokens"]),
            call=lambda: active_client.chat.completions.create(**kwargs),
        )
        if content and content.strip():
            return _success(response, provider)

        finish_reason = trace[-1].get("finish_reason", "") if trace else ""
        error_text = trace[-1].get("error", "") if trace else ""
        errors.append(f"{provider} JSON mode: {error_text or 'empty response'}")
        if any(marker in str(error_text).lower() for marker in ("insufficient balance", "error code: 402", "quota exhausted")):
            # A balance/quota failure cannot be repaired by changing prompt or
            # JSON mode.  Move directly to the configured alternate provider.
            primary_unavailable = True
            break
        print(
            f"LLM empty JSON response detected: provider={provider}, "
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

    if allow_plain_json_fallback and not primary_unavailable:
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
            "max_tokens": min(requested_max_tokens, get_provider_max_output_tokens(provider)),
        }
        if extra_kwargs:
            for key, value in extra_kwargs.items():
                # This is the primary provider's plain-JSON retry.  The
                # alternate provider is not selected until the loop below, so
                # do not reference fallback_provider in this scope.
                if key != "response_format":
                    fallback_kwargs[key] = value
        active_client = llm_client or client
        response, content = _attempt(
            attempt_provider=provider,
            attempt_model=str(fallback_kwargs["model"]),
            mode="plain_json",
            ordinal=resolved_retries + 1,
            max_output_tokens=int(fallback_kwargs["max_tokens"]),
            call=lambda: active_client.chat.completions.create(**fallback_kwargs),
        )
        if content and content.strip():
            print("LLM JSON fallback succeeded with plain-text JSON mode.")
            return _success(response, provider)
        errors.append(f"{provider} plain JSON mode: {trace[-1].get('error') or 'empty response'}")

    # The project can be configured with both providers. Use the alternate one
    # as an actual failover instead of silently returning an empty response.
    for fallback_provider in _provider_fallback_order(provider):
        fallback_client = _chat_client_for_provider(fallback_provider)
        fallback_model = get_long_output_model(fallback_provider) if long_output else _chat_model_for_provider(fallback_provider)
        fallback_kwargs = {
            "model": fallback_model,
            "messages": list(request_messages)
            + [{"role": "system", "content": "Return one non-empty valid compact JSON object only."}],
            "temperature": min(0.6, temperature),
            "max_tokens": min(requested_max_tokens, get_provider_max_output_tokens(fallback_provider)),
        }
        if extra_kwargs:
            for key, value in extra_kwargs.items():
                if key != "response_format":
                    fallback_kwargs[key] = value
        response, content = _attempt(
            attempt_provider=fallback_provider,
            attempt_model=fallback_model,
            mode="provider_failover_plain_json",
            ordinal=len(trace) + 1,
            max_output_tokens=int(fallback_kwargs["max_tokens"]),
            call=lambda: fallback_client.chat.completions.create(**fallback_kwargs),
        )
        if content and content.strip():
            print(f"LLM provider failover succeeded: from={provider}, to={fallback_provider}")
            return _success(response, fallback_provider)
        errors.append(f"{fallback_provider} plain JSON failover: {trace[-1].get('error') or 'empty response'}")

    detail = "; ".join(errors) or f"{provider} returned an empty JSON response"
    raise LLMJsonCompletionError(f"LLM JSON generation unavailable: {detail}", trace=trace)


def create_text_chat_completion(
    *,
    messages: List[dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = CASE_AI_MAX_TOKENS,
    llm_client: Optional[OpenAI] = None,
    return_trace: bool = False,
    long_output: bool = True,
    extra_kwargs: Optional[dict[str, Any]] = None,
):
    """Plain-text path for long scene templates when JSON transport is unusable."""
    provider = _provider_for_client(llm_client)
    requested = max(1, int(max_tokens))
    providers = [provider, *_provider_fallback_order(provider)]
    trace: list[dict[str, Any]] = []
    last_error = ""
    for ordinal, current_provider in enumerate(providers, start=1):
        active_client = (llm_client or client) if current_provider == provider else _chat_client_for_provider(current_provider)
        active_model = (model or get_chat_model()) if current_provider == provider else (
            get_long_output_model(current_provider) if long_output else _chat_model_for_provider(current_provider)
        )
        started = time.perf_counter()
        entry = {
            "provider": current_provider,
            "model": active_model,
            "mode": "plain_text_template",
            "attempt": ordinal,
            "max_tokens": min(requested, get_provider_max_output_tokens(current_provider)),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            request_kwargs = {
                "model": active_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": entry["max_tokens"],
            }
            if extra_kwargs and current_provider == provider:
                request_kwargs.update(extra_kwargs)
            response = active_client.chat.completions.create(**request_kwargs)
            content = extract_message_text(response)
            entry.update({
                "status": "success" if content.strip() else "empty",
                "finish_reason": _response_finish_reason(response),
                "response_chars": len(content),
                "duration_ms": round((time.perf_counter() - started) * 1000),
                **_response_usage(response),
            })
            trace.append(entry)
            if content.strip():
                result_trace = {
                    "primary_provider": provider,
                    "final_provider": current_provider,
                    "failed_attempts": sum(1 for item in trace if item.get("status") != "success"),
                    "switched_provider": current_provider != provider,
                    "attempts": trace,
                }
                return (response, result_trace) if return_trace else response
            last_error = f"{current_provider} returned empty text"
        except Exception as exc:
            last_error = _llm_error_summary(exc)
            entry.update({"status": "error", "error": last_error, "duration_ms": round((time.perf_counter() - started) * 1000)})
            trace.append(entry)
    raise LLMJsonCompletionError(f"LLM text template unavailable: {last_error}", trace=trace)


def create_case_completion_chat_completion(
    *,
    messages: List[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = CASE_AI_MAX_TOKENS,
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
