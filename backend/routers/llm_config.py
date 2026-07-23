import json
import os
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import models
from env_loader import BACKEND_ENV_PATH
from routers.auth import require_admin_user

router = APIRouter(prefix="/llm-config", tags=["LLM Config"])

PROVIDER_OPTIONS = {"qwen", "deepseek", "custom"}
STATIC_PROFILE_IDS = {"qwen", "deepseek"}
PROFILES_JSON_KEY = "LLM_PROFILES_JSON"
PROFILE_DEFAULTS = {
    "qwen": {
        "name": "通义千问 / 百炼",
        "chat_model": "qwen-plus",
        "long_output_model": "qwen-plus",
        "max_output_tokens": 32768,
    },
    "deepseek": {
        "name": "DeepSeek",
        "chat_model": "deepseek-v4-flash",
        "long_output_model": "deepseek-v4-flash",
        "max_output_tokens": 128000,
    },
    "custom": {
        "name": "内网本地模型",
        "chat_model": "",
        "long_output_model": "",
        "max_output_tokens": 32768,
    },
}
ENV_FIELDS = [
    "LLM_PROVIDER",
    "QWEN_BASE_URL",
    "QWEN_API_KEY",
    "BAILIAN_API_KEY",
    "DASHSCOPE_API_KEY",
    "BAILIAN_WORKSPACE_ID",
    "QWEN_WORKSPACE_ID",
    "DASHSCOPE_WORKSPACE_ID",
    "BAILIAN_REGION",
    "QWEN_CHAT_MODEL",
    "QWEN_LONG_OUTPUT_MODEL",
    "QWEN_MAX_OUTPUT_TOKENS",
    "QWEN_ASR_BASE_URL",
    "QWEN_ASR_MODEL",
    "QWEN_REALTIME_ASR_URL",
    "QWEN_REALTIME_ASR_MODEL",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_CHAT_MODEL",
    "DEEPSEEK_LONG_OUTPUT_MODEL",
    "DEEPSEEK_MAX_OUTPUT_TOKENS",
    "CUSTOM_LLM_BASE_URL",
    "CUSTOM_LLM_API_KEY",
    "CUSTOM_LLM_CHAT_MODEL",
    "CUSTOM_LLM_LONG_OUTPUT_MODEL",
    "CUSTOM_LLM_MAX_OUTPUT_TOKENS",
    "LLM_TIMEOUT_SECONDS",
    PROFILES_JSON_KEY,
]
MASKED_SECRET = "********"


class LlmProfilePayload(BaseModel):
    id: str = Field(default="", max_length=80)
    provider: str = Field(default="custom")
    name: str = Field(default="", max_length=120)
    base_url: str = Field(default="", max_length=500)
    api_key: str = Field(default="", max_length=1000)
    chat_model: str = Field(default="", max_length=120)
    long_output_model: str = Field(default="", max_length=120)
    max_output_tokens: int = Field(default=32768, ge=1, le=200000)
    workspace_id: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=60)
    asr_base_url: str = Field(default="", max_length=500)
    asr_model: str = Field(default="", max_length=120)
    realtime_url: str = Field(default="", max_length=500)
    realtime_model: str = Field(default="", max_length=120)


class LlmConfigPayload(BaseModel):
    timeout_seconds: int = Field(default=90, ge=5, le=1800)
    profiles: list[LlmProfilePayload] = Field(default_factory=list)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _mask_secret(value: str) -> str:
    return MASKED_SECRET if _clean(value) else ""


def _is_masked_secret(value: str) -> bool:
    return _clean(value) == MASKED_SECRET


def _normalize_provider(provider: str) -> str:
    normalized = _clean(provider).lower()
    if normalized in {"local", "openai", "openai_compatible"}:
        return "custom"
    return normalized if normalized in PROVIDER_OPTIONS else "custom"


def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not BACKEND_ENV_PATH.exists():
        return values
    for line in BACKEND_ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _quote_env_value(value: str) -> str:
    if not value:
        return ""
    if re.search(r"\s|#|=|\"", value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _write_env_values(updates: dict[str, str]) -> None:
    BACKEND_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = BACKEND_ENV_PATH.read_text(encoding="utf-8").splitlines() if BACKEND_ENV_PATH.exists() else []
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            next_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            next_lines.append(f"{key}={_quote_env_value(updates[key])}")
            seen.add(key)
        else:
            next_lines.append(line)

    missing = [key for key in ENV_FIELDS if key in updates and key not in seen]
    if missing:
        if next_lines and next_lines[-1].strip():
            next_lines.append("")
        next_lines.append("# LLM API profiles managed from admin console")
        for key in missing:
            next_lines.append(f"{key}={_quote_env_value(updates[key])}")

    BACKEND_ENV_PATH.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    for key, value in updates.items():
        os.environ[key] = value


def _resolve_runtime_or_file(values: dict[str, str], key: str, default: str = "") -> str:
    return _clean(os.getenv(key)) or _clean(values.get(key)) or default


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _provider_keys(provider: str) -> dict[str, str]:
    if provider == "qwen":
        return {
            "base_url": "QWEN_BASE_URL",
            "api_key": "QWEN_API_KEY",
            "chat_model": "QWEN_CHAT_MODEL",
            "long_output_model": "QWEN_LONG_OUTPUT_MODEL",
            "max_output_tokens": "QWEN_MAX_OUTPUT_TOKENS",
        }
    if provider == "deepseek":
        return {
            "base_url": "DEEPSEEK_BASE_URL",
            "api_key": "DEEPSEEK_API_KEY",
            "chat_model": "DEEPSEEK_CHAT_MODEL",
            "long_output_model": "DEEPSEEK_LONG_OUTPUT_MODEL",
            "max_output_tokens": "DEEPSEEK_MAX_OUTPUT_TOKENS",
        }
    return {
        "base_url": "CUSTOM_LLM_BASE_URL",
        "api_key": "CUSTOM_LLM_API_KEY",
        "chat_model": "CUSTOM_LLM_CHAT_MODEL",
        "long_output_model": "CUSTOM_LLM_LONG_OUTPUT_MODEL",
        "max_output_tokens": "CUSTOM_LLM_MAX_OUTPUT_TOKENS",
    }


def _profile_from_env(values: dict[str, str], provider: str, name: str) -> dict[str, Any]:
    keys = _provider_keys(provider)
    defaults = PROFILE_DEFAULTS[provider]
    chat_model = _resolve_runtime_or_file(values, keys["chat_model"], str(defaults["chat_model"]))
    base_url = _resolve_runtime_or_file(values, keys["base_url"])
    if provider == "deepseek" and base_url == "https://api.deepseek.com":
        base_url = ""
    profile = {
        "id": provider,
        "provider": provider,
        "name": name or str(defaults["name"]),
        "base_url": base_url,
        "api_key": _mask_secret(_resolve_runtime_or_file(values, keys["api_key"])),
        "chat_model": chat_model,
        "long_output_model": _resolve_runtime_or_file(values, keys["long_output_model"], str(defaults["long_output_model"]) or chat_model),
        "max_output_tokens": _safe_int(_resolve_runtime_or_file(values, keys["max_output_tokens"], str(defaults["max_output_tokens"])), int(defaults["max_output_tokens"])),
        "built_in": True,
    }
    if provider == "qwen":
        profile.update(
            {
                "workspace_id": _resolve_runtime_or_file(values, "BAILIAN_WORKSPACE_ID") or _resolve_runtime_or_file(values, "QWEN_WORKSPACE_ID"),
                "region": _resolve_runtime_or_file(values, "BAILIAN_REGION", "cn-beijing"),
                "asr_base_url": _resolve_runtime_or_file(values, "QWEN_ASR_BASE_URL"),
                "asr_model": _resolve_runtime_or_file(values, "QWEN_ASR_MODEL", "qwen3-asr-flash"),
                "realtime_url": _resolve_runtime_or_file(values, "QWEN_REALTIME_ASR_URL"),
                "realtime_model": _resolve_runtime_or_file(values, "QWEN_REALTIME_ASR_MODEL", "qwen3-asr-flash-realtime"),
            }
        )
    return profile


def _load_saved_custom_profiles(values: dict[str, str]) -> list[dict[str, Any]]:
    raw = _resolve_runtime_or_file(values, PROFILES_JSON_KEY)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []

    profiles: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        provider = _normalize_provider(str(item.get("provider") or "custom"))
        if provider != "custom":
            continue
        profile_id = _clean(item.get("id")) or f"custom-{len(profiles) + 1}"
        if profile_id in STATIC_PROFILE_IDS:
            continue
        profiles.append(
            {
                "id": profile_id,
                "provider": "custom",
                "name": _clean(item.get("name")) or "内网本地模型",
                "base_url": _clean(item.get("base_url")),
                "api_key": _mask_secret(_clean(item.get("api_key"))),
                "chat_model": _clean(item.get("chat_model")),
                "long_output_model": _clean(item.get("long_output_model")),
                "max_output_tokens": _safe_int(str(item.get("max_output_tokens") or ""), 32768),
                "built_in": False,
            }
        )
    return profiles


@router.get("")
def get_llm_config(_: models.User = Depends(require_admin_user)) -> dict[str, Any]:
    values = _read_env_file()
    profiles = [
        _profile_from_env(values, "qwen", "通义千问 / 百炼"),
        _profile_from_env(values, "deepseek", "DeepSeek"),
    ]

    saved_custom_profiles = _load_saved_custom_profiles(values)
    if saved_custom_profiles:
        profiles.extend(saved_custom_profiles)
    else:
        custom_profile = _profile_from_env(values, "custom", "内网本地模型")
        custom_profile["id"] = "custom-1"
        custom_profile["built_in"] = False
        profiles.append(custom_profile)

    return {
        "profiles": profiles,
        "timeout_seconds": _safe_int(_resolve_runtime_or_file(values, "LLM_TIMEOUT_SECONDS", "90"), 90),
        "env_path": str(BACKEND_ENV_PATH),
        "restart_required": False,
    }


@router.put("")
def save_llm_config(
    payload: LlmConfigPayload,
    _: models.User = Depends(require_admin_user),
) -> dict[str, Any]:
    existing_values = _read_env_file()
    raw_profiles = _resolve_runtime_or_file(existing_values, PROFILES_JSON_KEY)
    existing_custom_profiles: dict[str, dict[str, Any]] = {}
    if raw_profiles:
        try:
            parsed_profiles = json.loads(raw_profiles)
            if isinstance(parsed_profiles, list):
                existing_custom_profiles = {
                    _clean(item.get("id")): item
                    for item in parsed_profiles
                    if isinstance(item, dict) and _clean(item.get("id"))
                }
        except Exception:
            existing_custom_profiles = {}

    profiles: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in payload.profiles:
        provider = _normalize_provider(item.provider)
        profile_id = _clean(item.id) or f"{provider}-{len(profiles) + 1}"
        if profile_id in seen_ids:
            raise HTTPException(status_code=400, detail=f"配置卡片 ID 重复：{profile_id}")
        seen_ids.add(profile_id)

        keys = _provider_keys(provider)
        api_key = _clean(item.api_key)
        if _is_masked_secret(api_key):
            if provider == "custom" and profile_id in existing_custom_profiles:
                api_key = _clean(existing_custom_profiles[profile_id].get("api_key"))
            else:
                api_key = _resolve_runtime_or_file(existing_values, keys["api_key"])

        profile = {
            "id": profile_id,
            "provider": provider,
            "name": _clean(item.name) or ("通义千问 / 百炼" if provider == "qwen" else "DeepSeek" if provider == "deepseek" else "内网本地模型"),
            "base_url": _clean(item.base_url),
            "api_key": api_key,
            "chat_model": _clean(item.chat_model),
            "long_output_model": _clean(item.long_output_model) or _clean(item.chat_model),
            "max_output_tokens": int(item.max_output_tokens),
            "workspace_id": _clean(item.workspace_id),
            "region": _clean(item.region),
            "asr_base_url": _clean(item.asr_base_url),
            "asr_model": _clean(item.asr_model),
            "realtime_url": _clean(item.realtime_url),
            "realtime_model": _clean(item.realtime_model),
        }
        has_custom_content = bool(profile["base_url"] or profile["api_key"] or profile["chat_model"] or profile["long_output_model"])
        if provider == "custom" and has_custom_content and (not profile["base_url"] or not profile["chat_model"]):
            raise HTTPException(status_code=400, detail=f"{profile['name']} 请填写模型请求地址和模型名称")
        profiles.append(profile)

    qwen = next((item for item in profiles if item["provider"] == "qwen"), None)
    deepseek = next((item for item in profiles if item["provider"] == "deepseek"), None)
    custom_profiles = [item for item in profiles if item["provider"] == "custom"]

    updates = {
        "LLM_PROVIDER": "deepseek" if deepseek and deepseek["api_key"] else "qwen",
        "LLM_TIMEOUT_SECONDS": str(payload.timeout_seconds),
        PROFILES_JSON_KEY: json.dumps(custom_profiles, ensure_ascii=False, separators=(",", ":")),
    }

    for profile in (qwen, deepseek, next((item for item in custom_profiles if item["base_url"] and item["chat_model"]), None)):
        if not profile:
            continue
        keys = _provider_keys(profile["provider"])
        updates.update(
            {
                keys["base_url"]: profile["base_url"],
                keys["api_key"]: profile["api_key"],
                keys["chat_model"]: profile["chat_model"],
                keys["long_output_model"]: profile["long_output_model"],
                keys["max_output_tokens"]: str(profile["max_output_tokens"]),
            }
        )
        if profile["provider"] == "qwen":
            updates.update(
                {
                    "BAILIAN_API_KEY": profile["api_key"],
                    "DASHSCOPE_API_KEY": profile["api_key"],
                    "BAILIAN_WORKSPACE_ID": profile["workspace_id"],
                    "QWEN_WORKSPACE_ID": profile["workspace_id"],
                    "DASHSCOPE_WORKSPACE_ID": profile["workspace_id"],
                    "BAILIAN_REGION": profile["region"] or "cn-beijing",
                    "QWEN_ASR_BASE_URL": profile["asr_base_url"],
                    "QWEN_ASR_MODEL": profile["asr_model"] or "qwen3-asr-flash",
                    "QWEN_REALTIME_ASR_URL": profile["realtime_url"],
                    "QWEN_REALTIME_ASR_MODEL": profile["realtime_model"] or "qwen3-asr-flash-realtime",
                }
            )

    _write_env_values(updates)
    return {
        "message": "模型接口配置已保存，重启后端后生效",
        "restart_required": True,
        "env_path": str(BACKEND_ENV_PATH),
    }
