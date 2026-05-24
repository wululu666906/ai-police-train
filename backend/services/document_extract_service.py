from __future__ import annotations

import re
from io import BytesIO

from docx import Document


class DocumentExtractService:
    MAX_FILE_SIZE = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md"}

    @staticmethod
    def extract_pdf_text(file_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise ValueError("当前环境未安装 PDF 解析依赖 pypdf，请先安装后再使用 PDF 导入") from exc

        reader = PdfReader(BytesIO(file_bytes))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        text = "\n".join(texts).strip()
        if not text:
            raise ValueError("当前版本不支持图片 OCR，请上传可复制文字版 PDF 或 DOCX")
        return text

    @staticmethod
    def extract_docx_text(file_bytes: bytes) -> str:
        document = Document(BytesIO(file_bytes))
        texts = [paragraph.text for paragraph in document.paragraphs if paragraph.text and paragraph.text.strip()]
        text = "\n".join(texts).strip()
        if not text:
            raise ValueError("Word 文档未提取到有效正文，请检查文件内容后重试")
        return text

    @staticmethod
    def extract_markdown_text(file_bytes: bytes | str) -> str:
        if isinstance(file_bytes, str):
            text = file_bytes
            last_error = None
        else:
            last_error: Exception | None = None
            for encoding in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    text = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError as exc:
                    last_error = exc
            else:
                raise ValueError("Markdown 文档编码无法识别，请使用 UTF-8 或 GB18030 编码") from last_error

        text = re.sub(r"^\s{0,3}(#{1,6}|\- |\* |\+ |\d+\.)\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"`{1,3}", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = text.strip()
        if not text:
            raise ValueError("Markdown 文档未提取到有效正文，请检查文件内容后重试")
        return text

    @staticmethod
    def normalize_extracted_text(text: str) -> str:
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"^\s*\d+\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*第\s*\d+\s*页\s*$", "", cleaned, flags=re.MULTILINE)
        return cleaned.strip()

    def extract_text(self, filename: str, file_bytes: bytes) -> str:
        lower_name = (filename or "").lower()
        if lower_name.endswith(".pdf"):
            raw_text = self.extract_pdf_text(file_bytes)
        elif lower_name.endswith(".docx"):
            raw_text = self.extract_docx_text(file_bytes)
        elif lower_name.endswith(".md"):
            raw_text = self.extract_markdown_text(file_bytes)
        else:
            raise ValueError("仅支持 PDF、DOCX、MD 文件")

        normalized = self.normalize_extracted_text(raw_text)
        if not normalized:
            raise ValueError("文档未提取到有效正文，请检查文件内容后重试")
        return normalized


document_extract_service = DocumentExtractService()
