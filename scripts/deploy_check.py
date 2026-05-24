# -*- coding: utf-8 -*-
"""部署前检查：环境变量、构建产物、Docker 环境。"""
from __future__ import annotations

import os
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


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not ENV_PATH.exists():
        errors.append("缺少 backend/.env，请执行：cp backend/.env.example backend/.env")
    else:
        env = _load_env(ENV_PATH)
        secret = env.get("JWT_SECRET_KEY", "")
        if not secret or "replace-with" in secret.lower():
            errors.append("JWT_SECRET_KEY 仍为占位符，生产环境必须改为长随机字符串")
        if not (env.get("DASHSCOPE_API_KEY") or env.get("QWEN_API_KEY") or env.get("DEEPSEEK_API_KEY")):
            errors.append("未配置 LLM API Key（DASHSCOPE_API_KEY / QWEN_API_KEY / DEEPSEEK_API_KEY 至少一项）")

    for name in ("Dockerfile", "docker-compose.yml", "start.sh"):
        if not (ROOT / name).exists():
            errors.append(f"缺少部署文件：{name}")

    if not shutil.which("docker"):
        warnings.append("未检测到 docker 命令（在服务器上部署时需要安装 Docker）")

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
