from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def isolated_sys_path(*paths: str | Path) -> Iterator[None]:
    """Temporarily expose module paths without leaking them into the backend process."""
    original = list(sys.path)
    normalized = []
    for path in paths:
        value = str(Path(path).resolve())
        if value not in normalized:
            normalized.append(value)
    try:
        for value in reversed(normalized):
            if value not in sys.path:
                sys.path.insert(0, value)
        yield
    finally:
        sys.path[:] = original
