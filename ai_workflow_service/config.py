from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    service_name: str = "ai-police-workflow"
    host: str = os.getenv("AI_WORKFLOW_HOST", "0.0.0.0")
    port: int = int(os.getenv("AI_WORKFLOW_PORT", "8010"))
    internal_token: str = os.getenv("AI_WORKFLOW_INTERNAL_TOKEN", "")
    data_dir: Path = Path(os.getenv("AI_WORKFLOW_DATA_DIR", str(Path(__file__).parent / "data")))
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_ROLEPLAY_MODEL", "deepseek-chat")
    deepseek_timeout_seconds: float = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "45"))


settings = Settings()
