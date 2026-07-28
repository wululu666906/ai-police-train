import os


LEGACY_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LEGACY_DASHSCOPE_REALTIME_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
BAILIAN_TRIAL_BASE_URL = "https://trial.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
BAILIAN_TRIAL_REALTIME_URL = "wss://trial.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime"


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def qwen_api_key() -> str:
    return (
        _clean(os.getenv("QWEN_API_KEY"))
        or _clean(os.getenv("BAILIAN_API_KEY"))
        or _clean(os.getenv("DASHSCOPE_API_KEY"))
    )


def bailian_workspace_id() -> str:
    return (
        _clean(os.getenv("BAILIAN_WORKSPACE_ID"))
        or _clean(os.getenv("QWEN_WORKSPACE_ID"))
        or _clean(os.getenv("DASHSCOPE_WORKSPACE_ID"))
    )


def bailian_region() -> str:
    return _clean(os.getenv("BAILIAN_REGION")) or "cn-beijing"


def bailian_base_url(workspace_id: str | None = None) -> str:
    workspace = _clean(workspace_id) or bailian_workspace_id()
    if workspace:
        return f"https://{workspace}.{bailian_region()}.maas.aliyuncs.com/compatible-mode/v1"
    return BAILIAN_TRIAL_BASE_URL


def bailian_realtime_url(workspace_id: str | None = None) -> str:
    workspace = _clean(workspace_id) or bailian_workspace_id()
    if workspace:
        return f"wss://{workspace}.{bailian_region()}.maas.aliyuncs.com/api-ws/v1/realtime"
    return BAILIAN_TRIAL_REALTIME_URL


def _is_legacy_dashscope_url(value: str) -> bool:
    lowered = value.lower()
    return "dashscope.aliyuncs.com" in lowered and "maas.aliyuncs.com" not in lowered


def resolve_qwen_base_url(env_name: str = "QWEN_BASE_URL") -> str:
    configured = _clean(os.getenv(env_name))
    workspace = bailian_workspace_id()
    if configured:
        return configured
    if _clean(os.getenv("QWEN_ENDPOINT_PROVIDER")).lower() == "dashscope":
        return LEGACY_DASHSCOPE_BASE_URL
    return bailian_base_url(workspace)


def resolve_qwen_realtime_url(env_name: str = "QWEN_REALTIME_ASR_URL") -> str:
    configured = _clean(os.getenv(env_name))
    workspace = bailian_workspace_id()
    if configured:
        return configured
    if _clean(os.getenv("QWEN_ENDPOINT_PROVIDER")).lower() == "dashscope":
        return LEGACY_DASHSCOPE_REALTIME_URL
    return bailian_realtime_url(workspace)


def qwen_default_headers(endpoint_url: str | None = None) -> dict[str, str]:
    workspace = bailian_workspace_id()
    if not workspace:
        return {}
    lowered = _clean(endpoint_url).lower()
    if lowered and "maas.aliyuncs.com" not in lowered:
        return {}
    return {"X-DashScope-WorkSpace": workspace}
