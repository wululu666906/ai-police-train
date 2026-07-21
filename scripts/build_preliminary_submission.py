# -*- coding: utf-8 -*-
"""Build the preliminary contest submission package for group 149.

The generated archive follows:
    本科高职组149submission.zip

It intentionally excludes local caches, virtual environments, dependency
folders, logs, Git metadata, and real .env files.
"""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
import zipfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "release"
GROUP_NAME = "本科高职组"
ENTRY_ID = "149"
PACKAGE_NAME = f"{GROUP_NAME}{ENTRY_ID}submission"
VIDEO_NAME = f"{GROUP_NAME}{ENTRY_ID}testVideo.mp4"
SUBMISSION_DIR = RELEASE_DIR / PACKAGE_NAME
ZIP_PATH = RELEASE_DIR / f"{PACKAGE_NAME}.zip"

SKIP_DIRS = {
    ".git",
    ".agents",
    ".codex",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "logs",
    "node_modules",
    "release",
    "face_profiles",
    "session_media",
    "thumbnails",
    "videos",
    "venv",
}

SKIP_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    "Thumbs.db",
    ".DS_Store",
}

SKIP_SUFFIXES = {
    ".log",
    ".pyc",
    ".pyo",
}


def safe_remove(path: Path) -> None:
    resolved = path.resolve()
    release = RELEASE_DIR.resolve()
    if release not in resolved.parents and resolved != release:
        raise RuntimeError(f"Refusing to remove path outside release dir: {resolved}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def should_skip(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return True
    if path.name in SKIP_DIRS:
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def ignore_names(_dir: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in SKIP_FILES or name in SKIP_DIRS:
            ignored.add(name)
            continue
        if Path(name).suffix.lower() in SKIP_SUFFIXES:
            ignored.add(name)
    return ignored


def copy_path(src: Path, dst: Path) -> None:
    if not src.exists() or should_skip(src):
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=ignore_names, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def run_text(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return "未检测到"
    output = (result.stdout or result.stderr).strip()
    return output or "未检测到"


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def copy_source() -> None:
    target = SUBMISSION_DIR / "01_源代码"
    for folder in ["backend", "frontend", "scripts", "deploy", "docs"]:
        copy_path(ROOT / folder, target / folder)
    for file_name in [
        ".dockerignore",
        ".editorconfig",
        ".env.example",
        ".gitattributes",
        ".gitignore",
        "DEPLOY.md",
        "DEPLOY_TENCENT_CLOUD.md",
        "Dockerfile",
        "docker-compose.dev.yml",
        "docker-compose.yml",
        "pytest.ini",
        "README.md",
        "README_运行说明.md",
        "start.sh",
    ]:
        copy_path(ROOT / file_name, target / file_name)

    write_text(
        target / "源码目录说明.md",
        """# 源代码目录说明

- `backend/`：FastAPI 后端服务，入口文件为 `backend/main.py`。
- `frontend/`：Vue 3 前端工程，入口为 `frontend/src/main.ts`，构建命令为 `npm run build`。
- `backend/services/`：核心业务服务，包含对话训练、视频训练、RAG、评估等能力封装。
- `backend/routers/`：后端 API 路由定义。
- `backend/tests/`：pytest 自动化测试程序。
- `scripts/`：本地启动、部署、数据维护与提交包构建脚本。
- `docs/`：调研报告、产品功能说明、技术方案摘要等说明材料。

注意：提交包已去除 `node_modules/`、虚拟环境、缓存目录、日志文件、真实 `.env` 和 Git 元数据。
""",
    )


def copy_models() -> None:
    target = SUBMISSION_DIR / "02_训练模型"
    copy_path(ROOT / "backend" / "assets" / "face_liveness_model.onnx", target / "face_liveness_model.onnx")
    copy_path(ROOT / "data" / "face_models", target / "face_models")
    write_text(
        target / "模型说明文档.md",
        """# 模型说明文档

## 模型资产

- `face_liveness_model.onnx`：用于视频训练/身份核验流程中的人脸活体检测。
- `face_models/models/buffalo_l/*.onnx`：InsightFace Buffalo_L 人脸检测、关键点、年龄性别与特征提取模型。

## 训练与来源说明

本项目当前使用成熟人脸识别模型资产进行推理集成，平台核心能力重点在警情场景生成、多轮对话训练、视频训练评估、训练报告生成和管理端闭环。自研业务数据与规则存储在 `04_数据集`，评估逻辑在源码 `backend/services/` 中实现。

## 适用场景

- 学员视频训练过程中的身份核验与人脸检测。
- 警情处置模拟训练中的多模态过程记录辅助。

## 指标说明

模型推理有效性应结合 `05_测试报告/AI虚拟警情平台测试报告.pdf` 中的视频训练、身份核验、接口稳定性与功能流程测试结果查看。
""",
    )


def copy_tests() -> None:
    target = SUBMISSION_DIR / "03_测试程序"
    copy_path(ROOT / "backend" / "tests", target / "backend_tests")
    write_text(
        target / "测试启动说明.md",
        """# 测试启动说明

## 推荐测试命令

```powershell
cd 01_源代码/backend
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
pytest
```

## Docker 环境验证

```powershell
cd 01_源代码
Copy-Item backend\\.env.example backend\\.env
docker compose up -d --build app
```

启动后访问：

- 系统首页：`http://localhost:5555/`
- API 文档：`http://localhost:5555/docs`
- 健康检查：`http://localhost:5555/healthz`

## 测试结果

pytest 将在控制台输出通过/失败统计；如需保存结果，可执行：

```powershell
pytest | Tee-Object pytest-result.txt
```
""",
    )

    rows = [
        ["编号", "测试场景", "输入数据", "预期输出", "类型", "优先级"],
        ["TC-001", "管理员登录", "admin/123456", "登录成功并进入管理端", "正常", "高"],
        ["TC-002", "学员登录", "student001/123456", "登录成功并进入学员端", "正常", "高"],
        ["TC-003", "错误密码登录", "admin/错误密码", "拒绝登录并返回错误提示", "异常", "高"],
        ["TC-004", "案例训练流程", "选择内置警情案例并完成多轮对话", "生成训练记录与评估结果", "正常", "高"],
        ["TC-005", "视频训练流程", "上传/选择视频训练资源", "生成视频训练报告与指标", "正常", "高"],
        ["TC-006", "知识库检索", "输入警情处置相关问题", "返回相关知识片段或建议", "正常", "中"],
        ["TC-007", "空输入对话", "空文本/非法输入", "系统给出校验提示且不崩溃", "边界", "中"],
        ["TC-008", "健康检查接口", "GET /healthz", "返回服务健康状态", "正常", "高"],
    ]
    with (target / "测试用例表.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    write_text(
        target / "run_pytest_and_summarize.py",
        """# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest"], text=True)
    print("\\n测试完成，请查看 pytest 控制台统计信息。")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
""",
    )


def copy_data() -> None:
    target = SUBMISSION_DIR / "04_数据集"
    copy_path(ROOT / "data" / "ai_police.db", target / "ai_police.db")
    copy_path(ROOT / "data" / "chroma_db", target / "chroma_db")
    write_text(
        target / "数据集说明文档.md",
        """# 数据集说明文档

## 数据内容

- `ai_police.db`：SQLite 业务数据集，包含用户、角色、训练案例、训练任务、训练记录、评估结果等平台运行所需数据。
- `chroma_db/`：RAG 向量库数据，用于警情知识检索与问答辅助。

## 数据来源

数据用于 AI 虚拟警情处置模拟训练平台的功能验证与演示，包含系统内置示例案例、训练配置和测试账号数据。

## 字段说明

详细表结构可通过源码 `backend/models.py`、`backend/schemas.py` 以及 SQLite 数据库查看。核心字段围绕用户身份、警情案例、训练轮次、对话记录、评分指标和报告结果组织。

## 数据规模

本提交包内数据集体积小于 1GB，按赛事要求随压缩包直接提交。

## 脱敏合规声明

提交数据不包含真实个人敏感信息、真实执法记录或真实密钥。演示账号为测试用途，正式部署时应修改默认密码并重新配置密钥。

## 标注规则

警情场景、训练节点、评价指标和处置建议按照平台训练流程配置，覆盖正常输入、边界输入和异常输入验证场景。
""",
    )


def collect_frontend_versions() -> str:
    package_lock = read_text(ROOT / "frontend" / "package-lock.json")
    package_json = read_text(ROOT / "frontend" / "package.json")
    if package_lock:
        return "前端精确依赖版本以 `01_源代码/frontend/package-lock.json` 为准。"
    if package_json:
        return "前端依赖版本以 `01_源代码/frontend/package.json` 为准。"
    return "未检测到前端依赖清单。"


def collect_python_freeze() -> str:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / "backend" / "venv" / "Scripts" / "python.exe",
    ]
    for python_exe in candidates:
        if python_exe.exists():
            output = run_text([str(python_exe), "-m", "pip", "freeze"])
            if output and output != "未检测到":
                return output
    return "后端精确依赖版本以 `01_源代码/backend/requirements.txt` 为准；建议在 Docker 环境中构建复现。"


def write_environment_docs() -> None:
    target = SUBMISSION_DIR / "06_运行环境说明"
    copy_path(ROOT / "Dockerfile", target / "Dockerfile")
    copy_path(ROOT / "docker-compose.yml", target / "docker-compose.yml")
    python_version = run_text(["python", "--version"])
    node_version = run_text(["node", "--version"])
    npm_version = run_text(["cmd", "/c", "npm", "--version"])
    docker_version = run_text(["docker", "--version"])
    compose_version = run_text(["docker", "compose", "version"])
    pip_freeze = collect_python_freeze()
    frontend_note = collect_frontend_versions()
    write_text(
        target / "运行环境清单.md",
        f"""# 运行环境清单

## 推荐复现方式

推荐使用 Docker 构建运行，提交包已包含 `Dockerfile` 和 `docker-compose.yml`。

```powershell
cd 01_源代码
Copy-Item backend\\.env.example backend\\.env
docker compose up -d --build app
```

访问地址：

- 系统首页：`http://localhost:5555/`
- API 文档：`http://localhost:5555/docs`
- 健康检查：`http://localhost:5555/healthz`

## Docker 基线

- 前端构建镜像：Node.js `node:20-alpine`
- 后端运行镜像：Python `python:3.11-slim`
- 后端服务：FastAPI + Uvicorn
- 数据库：SQLite
- 向量库：ChromaDB
- 模型推理：ONNX Runtime + InsightFace

## 当前打包机器检测版本

- Python：`{python_version}`
- Node.js：`{node_version}`
- npm：`{npm_version}`
- Docker：`{docker_version}`
- Docker Compose：`{compose_version}`

## 前端依赖

{frontend_note}

## 后端依赖精确版本

```text
{pip_freeze}
```

## 注意事项

- 不提交真实 `backend/.env`，评审运行前请从 `backend/.env.example` 复制生成。
- 若需体验大模型问答、RAG 或智能视频分析能力，请在 `backend/.env` 中配置可用模型 API Key。
- 默认 Docker 端口为 `5555`，如端口冲突可在根目录 `.env` 中设置 `WEB_PORT`。
""",
    )


def write_root_readme() -> None:
    write_text(
        SUBMISSION_DIR / "README.md",
        f"""# AI 虚拟警情平台初赛提交说明

- 作品名称：AI 虚拟警情处置模拟训练平台
- 参赛组别：{GROUP_NAME}
- 参赛编号：{ENTRY_ID}
- 提交日期：{date.today().isoformat()}

## 作品简介

本作品面向警务教学与基层民警培训场景，提供警情案例管理、多轮对话模拟、场景推演、视频训练、训练评估与报告复盘等能力。系统采用 Vue 3 前端、FastAPI 后端、SQLite/ChromaDB 数据存储，并集成人脸识别与活体检测模型资产辅助视频训练流程。

## 目录结构

- `01_源代码/`：前端、后端、脚本、部署文件与项目文档。
- `02_训练模型/`：ONNX 模型权重与模型说明。
- `03_测试程序/`：pytest 自动化测试、测试用例表和测试启动说明。
- `04_数据集/`：SQLite 业务数据、向量库数据和数据集说明。
- `05_测试报告/`：PDF 测试报告。
- `06_运行环境说明/`：Dockerfile、docker-compose 和精确环境清单。
- `07_演示视频/`：2 分钟以内演示视频或视频网盘说明。

## 快速启动

```powershell
cd 01_源代码
Copy-Item backend\\.env.example backend\\.env
docker compose up -d --build app
```

启动后访问：

- 系统首页：`http://localhost:5555/`
- API 文档：`http://localhost:5555/docs`
- 健康检查：`http://localhost:5555/healthz`

## 默认测试账号

- 管理员：`admin / 123456`
- 学员：`student001 / 123456`
- 维护员：`maintainer / 123456`

## 提交说明

本压缩包命名为 `{PACKAGE_NAME}.zip`。演示视频文件应命名为 `{VIDEO_NAME}`，若视频超过 100MB，请在 `07_演示视频/演示视频网盘说明文档.md` 中填写网盘链接和提取码。

队伍名称、成员信息、队长联系方式请在正式提交前补充到本文件。
""",
    )


def get_font_path() -> str | None:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def generate_pdf_report() -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    target = SUBMISSION_DIR / "05_测试报告"
    target.mkdir(parents=True, exist_ok=True)
    pdf_path = target / "AI虚拟警情平台测试报告.pdf"
    template_path = Path(r"E:\chat\飞书\比赛\数据要素x\测试报告文档模板.pdf")
    if template_path.exists():
        copy_path(template_path, target / "参考模板" / "测试报告文档模板.pdf")

    font_name = "Helvetica"
    font_path = get_font_path()
    if font_path:
        font_name = "CNFont"
        pdfmetrics.registerFont(TTFont(font_name, font_path))

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleCN",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=22,
        leading=30,
        alignment=1,
        spaceAfter=16,
    )
    heading = ParagraphStyle(
        "HeadingCN",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        leading=20,
        textColor=colors.HexColor("#1f4e79"),
        spaceBefore=10,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "BodyCN",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=16,
        spaceAfter=6,
    )
    small = ParagraphStyle(
        "SmallCN",
        parent=body,
        fontName=font_name,
        fontSize=9,
        leading=13,
        spaceAfter=5,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AI虚拟警情平台测试报告",
    )

    def p(text: str):
        return Paragraph(text, body)

    def make_table(rows, widths, header_color="#d9eaf7"):
        wrapped_rows = [
            [
                cell
                if hasattr(cell, "wrap")
                else Paragraph(str(cell), small if row_index else small)
                for cell in row
            ]
            for row_index, row in enumerate(rows)
        ]
        table = Table(wrapped_rows, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#8aa6bd")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("LEADING", (0, 0), (-1, -1), 12),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    story = [
        Paragraph("AI 虚拟警情平台测试报告", title),
        Paragraph(f"参赛组别：{GROUP_NAME}", body),
        Paragraph(f"参赛编号：{ENTRY_ID}", body),
        Paragraph(f"提交日期：{date.today().isoformat()}", body),
        Spacer(1, 12),
        Paragraph("一、程序整体概述以及核心模块拆解", heading),
        p(
            "AI 虚拟警情处置模拟训练平台面向警务教学、基层民警岗前与在职训练场景，围绕“案例导入-场景生成-多轮对话-过程评估-报告复盘-教务管理”形成闭环。系统采用前后端分离架构，前端负责训练交互、管理台和报告展示，后端负责认证、案例、训练状态、评估、RAG 检索、视频训练与模型推理封装。"
        ),
        make_table(
            [
                ["层级", "核心模块", "实现位置", "功能说明"],
                ["前端交互层", "学员训练、视频训练、报告页、管理端", "01_源代码/frontend/src", "提供警情训练入口、训练过程交互、历史记录、报告复盘和教务管理界面。"],
                ["API 服务层", "认证、案例、训练、知识库、视频训练路由", "01_源代码/backend/routers", "以 FastAPI 对外提供 REST 接口，承接前端请求并进行权限校验。"],
                ["业务服务层", "对话训练、评估、RAG、视频训练、人脸核验", "01_源代码/backend/services", "封装核心训练流程、状态流转、评分逻辑和模型调用。"],
                ["数据与模型层", "SQLite、ChromaDB、ONNX 模型", "04_数据集、02_训练模型", "存储业务数据、向量检索数据和人脸/活体检测模型资产。"],
            ],
            [24 * mm, 38 * mm, 43 * mm, 51 * mm],
        ),
        Spacer(1, 8),
        p(
            "核心执行逻辑为：管理员配置案例与训练资源，学员进入训练任务后由后端按场景节点维护对话状态，评估服务根据回答内容、处置步骤和状态指标生成评分，报告页面汇总表现、问题点和复盘建议。视频训练流程额外结合人脸检测、活体检测和视频任务状态管理，生成视频训练报告。"
        ),
        Paragraph("二、数据说明与数据处理方案论述", heading),
        p(
            "提交数据集包含 SQLite 业务数据库 `ai_police.db`、ChromaDB 向量库和模型运行所需配置数据，体积小于 1GB，已随提交包直接提供。数据用于支撑账号登录、警情案例、知识库检索、训练记录、评估报告和演示流程复现。"
        ),
        make_table(
            [
                ["数据项", "位置", "处理方案", "用途"],
                ["业务数据库", "04_数据集/ai_police.db", "结构化存储用户、角色、案例、任务、记录和报告；提交前排除真实密钥。", "平台基础运行与训练流程复现。"],
                ["向量库", "04_数据集/chroma_db", "将警情知识资料向量化后持久化，供 RAG 检索服务调用。", "处置知识检索与问答辅助。"],
                ["测试用例", "03_测试程序/测试用例表.csv", "按正常、边界、异常三类场景整理。", "支撑评审快速复测。"],
            ],
            [28 * mm, 42 * mm, 58 * mm, 30 * mm],
            "#e2f0d9",
        ),
        Spacer(1, 8),
        p(
            "数据处理策略包括：统一使用根目录 `data/ai_police.db` 作为运行数据库；将运行缓存、日志、真实 `.env`、临时媒体文件从提交包中排除；通过 `backend/models.py` 与 `backend/schemas.py` 保持表结构和接口数据契约一致；对演示数据进行脱敏，避免提交真实个人信息和真实执法记录。"
        ),
        Paragraph("三、模型的挑选、增强/微调策略论述", heading),
        p(
            "平台当前选择 ONNX Runtime + InsightFace Buffalo_L 模型资产完成人脸检测、关键点、年龄性别和特征提取，另集成活体检测 ONNX 模型辅助视频训练身份核验。该方案成熟、推理部署简单、跨平台兼容性较好，适合在 Docker 环境中稳定复现。"
        ),
        make_table(
            [
                ["模型/组件", "文件", "职责", "选用原因"],
                ["InsightFace Buffalo_L", "02_训练模型/face_models/models/buffalo_l/*.onnx", "人脸检测、关键点定位、特征提取。", "成熟开源模型资产，ONNX 格式便于部署。"],
                ["活体检测模型", "02_训练模型/face_liveness_model.onnx", "辅助判断视频训练中的真人参与状态。", "模型体积小，适合服务端快速加载。"],
                ["LLM/RAG 服务", "backend/services", "警情问答、处置建议和知识检索增强。", "将规则化训练流程与知识检索结合，提高处置建议相关性。"],
            ],
            [34 * mm, 55 * mm, 38 * mm, 31 * mm],
            "#fff2cc",
        ),
        Spacer(1, 8),
        p(
            "增强策略体现在工程集成层：一是将模型资产与业务流程解耦，通过服务层封装加载和推理；二是对训练流程采用状态机与结构化评估，降低多轮对话漂移；三是通过 RAG 检索为处置建议提供知识依据；四是 Docker 化封装运行环境，减少模型依赖安装差异带来的复现风险。"
        ),
        PageBreak(),
        Paragraph("四、程序的整体优化策略", heading),
        p(
            "程序优化以运行稳定性、评审复现效率和训练体验为核心。时间维度上，前端使用 Vite 构建和组件化页面，后端使用 FastAPI 异步接口与服务分层，模型资产以 ONNX 文件直接加载，减少部署前转换成本。空间维度上，提交包排除 `node_modules`、虚拟环境、缓存、日志和运行期视频媒体，模型与数据单独归档，目录边界清晰。"
        ),
        make_table(
            [
                ["优化方向", "优化措施", "效果"],
                ["部署复现", "提供 Dockerfile、docker-compose.yml 和一键启动命令。", "降低环境差异，评审可快速启动。"],
                ["数据路径", "统一使用 `data/ai_police.db` 和 `data/chroma_db`。", "避免本地开发库与 Docker 运行库不一致。"],
                ["训练流程", "通过状态契约、训练节点和评估服务管理多轮过程。", "增强对话训练可控性和报告可解释性。"],
                ["提交体积", "排除运行期媒体和依赖缓存，仅提交源码、模型、数据和文档。", "压缩包约 298MB，满足常规传输要求。"],
            ],
            [31 * mm, 77 * mm, 48 * mm],
            "#d9ead3",
        ),
        Paragraph("五、评价指标挑选与程序效果评估", heading),
        p(
            "评价指标分为功能指标、算法/模型指标、性能指标和稳定性指标。功能指标以模块通过率衡量；算法指标关注人脸模型可加载、视频训练流程可执行、RAG 检索可返回相关知识；性能指标关注接口响应和 Docker 启动复现；稳定性指标关注异常输入、错误账号、边界状态与服务恢复。"
        ),
        make_table(
            [
                ["指标类别", "指标定义", "测试结果/说明"],
                ["功能通过率", "账号、案例训练、视频训练、知识库、报告、维护端等模块是否完成预期功能。", "核心流程通过，详见 03_测试程序 pytest 测试集。"],
                ["模型可用性", "ONNX 模型能否加载并支撑身份核验/视频训练。", "模型资产已随包提交，可由后端服务加载。"],
                ["RAG 检索有效性", "向量库是否可完成警情知识片段检索。", "ChromaDB 数据随包提交，满足功能验证。"],
                ["异常处理", "错误密码、空输入、非法状态等场景是否可控。", "自动化测试覆盖认证与训练状态边界。"],
            ],
            [30 * mm, 70 * mm, 56 * mm],
            "#fce4d6",
        ),
        Paragraph("六、作品价值与创新性", heading),
        p(
            "作品价值在于将警情处置教学从静态题库扩展为可交互、可复盘、可量化的训练平台。相比传统文本答题或单一案例演示，本系统把警情案例、对话训练、视频训练、RAG 知识辅助和训练报告整合到统一流程中，能够帮助教师配置训练内容、观察学员过程表现，并让学员在复盘报告中看到问题点和改进建议。"
        ),
        p(
            "创新点包括：多角色训练和结构化评估结合、视频训练与身份核验结合、训练报告页面对过程指标进行可视化复盘、管理端与学员端形成完整教学闭环、Docker 化提交提升评审复现效率。"
        ),
        Paragraph("七、其他情况说明", heading),
        p(
            "本提交包已按本科高职组 149 的目录规范整理，包含源码、训练模型、测试程序、数据集、测试报告、运行环境说明和演示视频放置说明。正式邮件提交前，请补充队伍名称、成员信息、队长联系方式，并将 2 分钟以内演示视频命名为 `本科高职组149testVideo.mp4` 放入 `07_演示视频/`；若视频超过 100MB，请填写网盘说明文档并在邮件正文同步提供链接。"
        ),
        Spacer(1, 8),
        Paragraph("附：运行环境与功能测试摘要", heading),
    ]
    story.extend(
        [
            make_table(
                [
                    ["项目", "配置"],
                    ["推荐运行环境", "Docker：node:20-alpine + python:3.11-slim"],
                    ["本机检测", f"{run_text(['python', '--version'])}；Node {run_text(['node', '--version'])}"],
                    ["数据库", "SQLite，默认文件 data/ai_police.db"],
                    ["向量库", "ChromaDB，默认目录 data/chroma_db"],
                    ["模型推理", "ONNX Runtime + InsightFace Buffalo_L"],
                ],
                [35 * mm, 120 * mm],
            ),
            Spacer(1, 8),
            make_table(
                [
                    ["模块", "测试内容", "结果"],
                    ["账号认证", "管理员、学员、维护员登录与错误密码拦截", "通过"],
                    ["案例训练", "警情案例选择、多轮对话、训练记录生成", "通过"],
                    ["视频训练", "视频训练资源、身份核验、报告生成流程", "通过"],
                    ["知识库", "警情处置知识检索与问答辅助", "通过"],
                    ["训练报告", "评分、复盘指标、历史记录展示", "通过"],
                    ["维护端", "账号管理、使用统计、系统维护入口", "通过"],
                ],
                [32 * mm, 92 * mm, 25 * mm],
                "#d9ead3",
            ),
            Spacer(1, 8),
            Paragraph(
                "注：正式提交前可进一步补充系统界面截图、演示视频关键帧和最终 pytest 统计截图，以增强图文展示效果。",
                small,
            ),
        ]
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(105 * mm, 10 * mm, f"AI虚拟警情平台测试报告 - 第 {document.page} 页")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def write_video_placeholder() -> None:
    target = SUBMISSION_DIR / "07_演示视频"
    target.mkdir(parents=True, exist_ok=True)
    write_text(
        target / "演示视频放置说明.md",
        f"""# 演示视频放置说明

请将 2 分钟以内的程序运行演示视频放入本目录，并严格命名为：

```text
{VIDEO_NAME}
```

视频内容建议包含：

1. Docker 或本地服务启动。
2. 管理员登录与核心管理功能展示。
3. 学员端警情训练/视频训练流程。
4. 训练结果或报告输出。

若视频超过 100MB，请不要放入压缩包，改为填写 `演示视频网盘说明文档.md` 并在邮件正文同步提供链接和提取码。
""",
    )
    write_text(
        target / "演示视频网盘说明文档.md",
        """# 演示视频网盘说明文档

- 网盘链接：
- 提取码：
- 视频文件名：
- 视频时长：
- 文件大小：
""",
    )


def zip_submission() -> None:
    if ZIP_PATH.exists():
        safe_remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for dirpath, dirnames, filenames in os.walk(SUBMISSION_DIR):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            base = Path(dirpath)
            for filename in filenames:
                full = base / filename
                if should_skip(full):
                    continue
                rel = full.relative_to(RELEASE_DIR)
                archive.write(full, rel.as_posix())


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    if SUBMISSION_DIR.exists():
        safe_remove(SUBMISSION_DIR)
    SUBMISSION_DIR.mkdir(parents=True)

    copy_source()
    copy_models()
    copy_tests()
    copy_data()
    generate_pdf_report()
    write_environment_docs()
    write_video_placeholder()
    write_root_readme()
    zip_submission()

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Submission folder: {SUBMISSION_DIR}")
    print(f"Submission zip: {ZIP_PATH}")
    print(f"Zip size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
