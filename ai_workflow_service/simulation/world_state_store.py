from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Iterator


class WorldStateStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_lock = Lock()
        self._session_locks: dict[str, RLock] = {}

    def _safe_id(self, workflow_id: str) -> str:
        value = "".join(ch for ch in workflow_id if ch.isalnum() or ch in "-_")[:128]
        if not value:
            raise ValueError("workflow_id 无效")
        return value

    def _path(self, workflow_id: str) -> Path:
        return self.root / f"{self._safe_id(workflow_id)}.json"

    @contextmanager
    def locked(self, workflow_id: str) -> Iterator[None]:
        safe_id = self._safe_id(workflow_id)
        with self._index_lock:
            lock = self._session_locks.setdefault(safe_id, RLock())
        with lock:
            yield

    @property
    def writable(self) -> bool:
        try:
            probe = self.root / ".write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        path = self._path(workflow_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def put(self, workflow_id: str, value: dict[str, Any]) -> None:
        path = self._path(workflow_id)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(temp, path)
