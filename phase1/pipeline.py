"""OCR -> DOCX 自动化流水线核心（Phase 1）。

复用 provider.py / ocrdoc_schema.py / docx_builder.py，不修改它们。

职责：
- 文件写入完成检测（is_file_stable）
- SHA256 去重（ProcessRecordStore + processed.json）
- OCR -> OCRDocument JSON -> DOCX（Pipeline.process_image）
- 异常处理（失败移到 failed/）
"""

import hashlib
import json
import logging
import shutil
import sys
import time
from pathlib import Path

# 复用 phase0 已验证模块（provider / ocrdoc_schema / docx_builder）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase0"))

from docx_builder import render_document
from ocrdoc_schema import extract_json_from_text, validate_ocr_document
from provider import MIME_TYPES, ProviderError

logger = logging.getLogger("pipeline")


def is_file_stable(path, interval=1.0, checks=2):
    """判断文件是否写入完成：连续 checks 次采样大小相同 + 可正常读取。"""
    path = Path(path)
    if not path.exists():
        return False
    try:
        size = path.stat().st_size
        for _ in range(checks - 1):
            time.sleep(interval)
            if not path.exists():
                return False
            new_size = path.stat().st_size
            if new_size != size:
                return False
            size = new_size
        path.read_bytes()
        return True
    except OSError:
        return False


class ProcessRecordStore:
    """processed.json 读写，用于 SHA256 去重。"""

    def __init__(self, path):
        self.path = Path(path)
        self.records = {}
        if self.path.exists():
            try:
                self.records = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("processed.json 解析失败，将视为空记录")
                self.records = {}

    def is_processed(self, sha256):
        """仅当之前 OCR 与 DOCX 都成功时才算已处理。"""
        rec = self.records.get(sha256)
        return bool(rec and rec.get("ocr_success") and rec.get("docx_success"))

    def set(self, sha256, record):
        self.records[sha256] = record
        self._save()

    def _save(self):
        self.path.write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class Pipeline:
    """单张图片的完整处理流水线。"""

    def __init__(self, provider, input_dir, output_dir, failed_dir, store, xsl_path=None,
                 move_failed=True):
        self.provider = provider
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.failed_dir = Path(failed_dir)
        self.store = store
        self.xsl_path = xsl_path
        self.move_failed = move_failed
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    def process_image(self, image_path):
        """处理单张图片，返回状态字符串。

        返回：success / failed / skipped_duplicate / skipped_unsupported / skipped_not_stable
        """
        image_path = Path(image_path)
        name = image_path.name

        mime = MIME_TYPES.get(image_path.suffix.lower())
        if mime is None:
            logger.warning("不支持的格式，跳过：%s", name)
            return "skipped_unsupported"

        try:
            image_bytes = image_path.read_bytes()
        except OSError as exc:
            logger.warning("读取失败（可能未写完）：%s（%s）", name, exc)
            return "skipped_not_stable"

        sha256 = hashlib.sha256(image_bytes).hexdigest()

        # 去重：同一内容已成功处理过则不再调用 AI
        if self.store.is_processed(sha256):
            logger.info("内容已处理过（SHA256 相同），跳过：%s", name)
            return "skipped_duplicate"

        stem = image_path.stem
        json_path = self._available_output(stem, ".json")
        docx_path = self._available_output(stem, ".docx")

        record = {
            "path": str(image_path),
            "sha256": sha256,
            "processed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ocr_success": False,
            "docx_success": False,
            "output_json": str(json_path),
            "output_docx": str(docx_path),
            "error": None,
        }

        # 1) OCR -> OCRDocument JSON
        try:
            raw_text = self.provider.recognize(image_bytes, mime)
            data = extract_json_from_text(raw_text)
            errors = validate_ocr_document(data)
            if errors:
                raise ValueError("Schema 校验失败: {}".format(errors[0].message))
            record["ocr_success"] = True
        except (ProviderError, ValueError) as exc:
            record["error"] = "OCR 失败: {}".format(exc)
            return self._on_failure(image_path, record)

        # 注入 meta（AI 不负责填 sha256/路径等文件属性）
        data.setdefault("schema_version", "1.0")
        data["meta"] = {
            "source_path": str(image_path),
            "sha256": sha256,
            "language": "zh-CN",
        }

        try:
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            record["error"] = "JSON 写入失败: {}".format(exc)
            return self._on_failure(image_path, record)

        # 2) DOCX
        try:
            render_document(data, str(docx_path), self.xsl_path)
            record["docx_success"] = True
        except Exception as exc:
            record["error"] = "DOCX 生成失败: {}".format(exc)
            return self._on_failure(image_path, record)

        self.store.set(sha256, record)
        logger.info("处理成功：%s -> %s, %s", name, json_path.name, docx_path.name)
        return "success"

    def _available_output(self, stem, suffix):
        """生成不覆盖已有文件的输出路径。"""
        base = self.output_dir / (stem + suffix)
        if not base.exists():
            return base
        ts = time.strftime("%Y%m%d_%H%M%S")
        return self.output_dir / "{}_{}{}".format(stem, ts, suffix)

    def _on_failure(self, image_path, record):
        """失败处理：记录，并按配置决定是否移到 failed/。"""
        self.store.set(record["sha256"], record)
        if not self.move_failed:
            logger.error("处理失败，保留原文件：%s（%s）", image_path.name, record["error"])
            return "failed"
        dest = self.failed_dir / image_path.name
        if dest.exists():
            dest = self.failed_dir / "{}_{}{}".format(
                image_path.stem, time.strftime("%Y%m%d_%H%M%S"), image_path.suffix
            )
        try:
            shutil.move(str(image_path), str(dest))
            logger.error("处理失败，已移到 failed/：%s（%s）", image_path.name, record["error"])
        except OSError as exc:
            logger.error("处理失败且移动失败：%s（%s）", image_path.name, exc)
        return "failed"
