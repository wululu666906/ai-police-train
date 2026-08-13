from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any


class JsonStateStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _path(self, workflow_id: str) -> Path:
        safe_id = "".join(ch for ch in workflow_id if ch.isalnum() or ch in "-_" )[:128]
        if not safe_id:
            raise ValueError("workflow_id 无效")
        return self.root / f"{safe_id}.json"

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        path = self._path(workflow_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, workflow_id: str, value: dict[str, Any]) -> None:
        path = self._path(workflow_id)
        temp = path.with_suffix(".tmp")
        with self._lock:
            temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, path)
