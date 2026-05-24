# -*- coding: utf-8 -*-
"""Create a clean source-code zip for delivery (no deps, secrets, or runtime data)."""
from __future__ import annotations

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "release"
DATE = datetime.now().strftime("%Y%m%d")
ZIP_NAME = f"AI虚拟警情处置模拟训练平台-源码-{DATE}.zip"

# Directory names to skip anywhere in the tree
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "chroma_db",
    "data",
    "logs",
    "backups",
    "release",
    "deploy_cloud_bundle",
    "deploy_native_bundle",
    "duiyou",
    ".vscode",
    ".idea",
    ".cursor",
}

# File names or suffixes to skip
SKIP_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "fileio.json",
    "result.txt",
    "temp_transcript.md",
    "temp_transcript_utf8.md",
}
SKIP_FILE_SUFFIXES = (
    ".db",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".zip",
    ".tar.gz",
    ".tgz",
    ".log",
)
SKIP_NAME_CONTAINS = (".bak", "preview.json", "-preview.")
SKIP_FILE_PREFIXES = ("~$",)


def should_skip(path: Path, rel: Path) -> bool:
    parts = rel.parts
    if any(p in SKIP_DIR_NAMES for p in parts):
        return True
    name = path.name
    if name in SKIP_FILE_NAMES:
        return True
    if any(name.endswith(s) for s in SKIP_FILE_SUFFIXES):
        return True
    if any(token in name for token in SKIP_NAME_CONTAINS):
        return True
    if any(name.startswith(p) for p in SKIP_FILE_PREFIXES):
        return True
    if name in {".DS_Store", "Thumbs.db"}:
        return True
    return False


def pack_readme() -> str:
    return f"""AI虚拟警情处置模拟训练平台 — 源码包说明
========================================

生成日期: {DATE}

本压缩包为「可部署源码」，不含以下内容（需自行安装或生成）：
  - Python 虚拟环境 (backend/venv)
  - 前端依赖 (frontend/node_modules)
  - 前端构建产物 (frontend/dist，执行 npm run build 生成)
  - 数据库文件 (*.db)、向量库 (chroma_db)、日志 (logs)
  - 环境变量文件 (.env，请从 .env.example 复制后填写)

快速开始
--------
1. 解压到目标目录
2. 阅读根目录 README.md 与 DEPLOY.md（云服务器部署）
3. 后端:
     cd backend
     python -m venv venv
     venv\\Scripts\\activate
     pip install -r requirements.txt
     copy .env.example .env
     python init_db.py
     uvicorn main:app --host 127.0.0.1 --port 8000
4. 前端:
     cd frontend
     npm install
     copy .env.example .env.local
     npm run dev

生产部署可使用根目录 docker-compose.yml。

文档目录 docs/ 含调研报告、产品说明与技术摘要。
"""


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RELEASE_DIR / ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            # Prune walk in place
            dirnames[:] = [
                d
                for d in dirnames
                if d not in SKIP_DIR_NAMES and d not in {".git"}
            ]
            base = Path(dirpath)
            for fname in filenames:
                full = base / fname
                rel = full.relative_to(ROOT)
                if should_skip(full, rel):
                    continue
                zf.write(full, rel.as_posix())
                file_count += 1

        zf.writestr("打包说明.txt", pack_readme().encode("utf-8"))

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"OK: {zip_path}")
    print(f"Files: {file_count}, Size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
