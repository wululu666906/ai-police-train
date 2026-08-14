from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(Path(__file__).resolve().parent / ".env")


@dataclass(frozen=True)
class Settings:
    service_name: str = "ai-police-workflow"
    host: str = os.getenv("AI_WORKFLOW_HOST", "0.0.0.0")
    port: int = int(os.getenv("AI_WORKFLOW_PORT", "8020"))
    internal_token: str = os.getenv("AI_WORKFLOW_INTERNAL_TOKEN", "")
    data_dir: Path = Path(os.getenv("AI_WORKFLOW_DATA_DIR", str(Path(__file__).parent / "data")))
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
    deepseek_model: str = os.getenv("DEEPSEEK_CHAT_MODEL") or "deepseek-v4-flash"
    deepseek_timeout_seconds: float = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45"))
    deepseek_reasoning_mode: str = (os.getenv("DEEPSEEK_REASONING_MODE") or "disabled").strip().lower()
    complete_story_max_tokens: int = max(8000, int(os.getenv("COMPLETE_STORY_MAX_TOKENS") or os.getenv("CASE_STORY_MAX_TOKENS") or "24000"))
    complete_story_reasoning_mode: str = (os.getenv("COMPLETE_STORY_REASONING_MODE") or os.getenv("CASE_STORY_REASONING_MODE") or "enabled").strip().lower()
    complete_story_reasoning_effort: str = (os.getenv("COMPLETE_STORY_REASONING_EFFORT") or os.getenv("CASE_STORY_REASONING_EFFORT") or "max").strip().lower()
    tinytroupe_mode: str = (os.getenv("TINY_TROUPE_MODE") or "world").strip().lower()
    tinytroupe_max_actors: int = max(1, min(6, int(os.getenv("TINY_TROUPE_MAX_ACTORS", "6"))))
    tinytroupe_model_concurrency: int = max(1, min(6, int(os.getenv("TINY_TROUPE_MODEL_CONCURRENCY", "6"))))
    tinytroupe_max_tokens: int = max(400, int(os.getenv("TINY_TROUPE_MAX_TOKENS", "1600")))
    tinytroupe_state_version: int = 1


settings = Settings()
