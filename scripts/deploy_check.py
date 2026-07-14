# -*- coding: utf-8 -*-
"""部署前检查：环境变量、构建产物、Docker 环境。"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
ENV_EXAMPLE = ROOT / "backend" / ".env.example"
TEXT_SCAN_EXTENSIONS = {
    ".py",
    ".vue",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".css",
    ".scss",
    ".html",
    ".json",
    ".md",
    ".sh",
    ".ps1",
    ".conf",
    ".yml",
    ".yaml",
}
TEXT_SCAN_DIRS = ("backend", "frontend/src", "frontend/public", "scripts", "deploy")
TEXT_SCAN_EXCLUDE_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "history-artifacts-preview.json",
    "history-artifacts-apply.json",
}
REPLACEMENT_CHAR_ALLOWLIST = {
    Path("backend/services/text_repair.py"),
}
TEXT_SCAN_EXCLUDE_PARTS = {
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "site-packages",
    "venv",
    ".venv",
    "mediapipe",
}
QUESTION_DAMAGE_RE = re.compile(r"\?{3,}")


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ))


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for rel_dir in TEXT_SCAN_DIRS:
        base = ROOT / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in TEXT_SCAN_EXCLUDE_PARTS for part in path.relative_to(ROOT).parts):
                continue
            if path.name in TEXT_SCAN_EXCLUDE_NAMES:
                continue
            if path.suffix.lower() in TEXT_SCAN_EXTENSIONS:
                files.append(path)
    return files


def _check_text_encoding() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in _iter_text_files():
        rel_path = path.relative_to(ROOT)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{rel_path} 不是合法 UTF-8：{exc}")
            continue
        if "\ufffd" in text:
            if rel_path not in REPLACEMENT_CHAR_ALLOWLIST:
                errors.append(f"{rel_path} 含 Unicode 替换字符 U+FFFD，疑似曾按错误编码读取后保存")
        for line_no, line in enumerate(text.splitlines(), start=1):
            match = QUESTION_DAMAGE_RE.search(line)
            if not match:
                continue
            snippet = line.strip()
            if len(snippet) > 96:
                snippet = snippet[:93] + "..."
            errors.append(f"{rel_path}:{line_no} 含连续问号 {match.group(0)!r}，疑似中文已不可逆替换：{snippet}")
    return errors, warnings


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not ENV_PATH.exists():
        errors.append("缺少 backend/.env，请执行：cp backend/.env.example backend/.env")
    else:
        env = _load_env(ENV_PATH)
        secret = env.get("JWT_SECRET_KEY") or env.get("SECRET_KEY", "")
        if not secret or "replace-with" in secret.lower():
            errors.append("JWT_SECRET_KEY 仍为占位符，生产环境必须改为长随机字符串")
        elif env.get("SECRET_KEY") and not env.get("JWT_SECRET_KEY"):
            warnings.append("检测到旧变量 SECRET_KEY，建议改为 JWT_SECRET_KEY（代码已兼容两者）")
        if not (env.get("DASHSCOPE_API_KEY") or env.get("QWEN_API_KEY") or env.get("DEEPSEEK_API_KEY")):
            errors.append("未配置 LLM API Key（DASHSCOPE_API_KEY / QWEN_API_KEY / DEEPSEEK_API_KEY 至少一项）")

    for name in ("Dockerfile", "docker-compose.yml", "start.sh"):
        if not (ROOT / name).exists():
            errors.append(f"缺少部署文件：{name}")

    if not shutil.which("docker"):
        warnings.append("未检测到 docker 命令（在服务器上部署时需要安装 Docker）")

    encoding_errors, encoding_warnings = _check_text_encoding()
    errors.extend(encoding_errors)
    warnings.extend(encoding_warnings)

    data_dir = ROOT / "data"
    if not data_dir.exists():
        warnings.append("data/ 目录不存在，首次 docker compose 前将自动创建")

    _safe_print("=== 部署前检查 ===\n")
    if warnings:
        _safe_print("提示：")
        for item in warnings:
            _safe_print(f"  - {item}")
        _safe_print("")

    if errors:
        _safe_print("必须修复：")
        for item in errors:
            _safe_print(f"  [X] {item}")
        _safe_print(f"\n参考：{ROOT / 'DEPLOY.md'}")
        return 1

    _safe_print("[OK] 部署文件与环境变量检查通过，可执行：")
    _safe_print("  docker compose up -d --build")
    _safe_print("  或 bash scripts/server_deploy.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
