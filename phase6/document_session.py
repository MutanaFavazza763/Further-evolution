"""OCRDocument 编辑会话，与 UI 和 Word 导出保持解耦。"""

import json
import os
from pathlib import Path

from phase0.ocrdoc_schema import validate_ocr_document


class DocumentSession:
    """管理 OCRDocument 的原始 JSON、校验和保存。"""

    def __init__(self):
        self.path = None
        self.raw_text = ""

    def load(self, path):
        """加载 JSON 文件；语法错误会抛出 ValueError。"""
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("无法加载 OCRDocument：{}".format(exc)) from exc
        self.path = path
        self.raw_text = json.dumps(data, ensure_ascii=False, indent=2)
        return data

    def parse(self):
        """解析当前编辑内容，返回 OCRDocument dict。"""
        try:
            data = json.loads(self.raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON 格式错误：{}".format(exc.msg)) from exc
        if not isinstance(data, dict):
            raise ValueError("OCRDocument 顶层必须是 JSON 对象")
        return data

    def validation_messages(self):
        """返回当前内容的语法或 Schema 错误消息；空列表表示可保存。"""
        try:
            data = self.parse()
        except ValueError as exc:
            return [str(exc)]
        return [error.message for error in validate_ocr_document(data)]

    def block_summaries(self):
        """返回用于 UI 列表预览的 block 摘要。"""
        try:
            blocks = self.parse().get("blocks", [])
        except ValueError:
            return []
        if not isinstance(blocks, list):
            return []

        summaries = []
        for index, block in enumerate(blocks):
            if not isinstance(block, dict):
                summaries.append("{}: 无效 block".format(index + 1))
                continue
            block_type = block.get("type", "unknown")
            text = block.get("text", "")
            if not text:
                runs = block.get("runs", [])
                text = "".join(
                    run.get("text", "") or run.get("latex", "")
                    for run in runs if isinstance(run, dict)
                )
            if not text and block_type == "formula":
                text = block.get("latex", "")
            text = " ".join(str(text).split())[:60]
            summaries.append("{}: {}  {}".format(index + 1, block_type, text))
        return summaries

    def save(self, path=None):
        """校验后原子写入 JSON；未传路径时覆盖已加载文件。"""
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("请先选择保存位置")
        messages = self.validation_messages()
        if messages:
            raise ValueError("无法保存：{}".format(messages[0]))

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            temporary.write_text(self.raw_text + "\n", encoding="utf-8")
            os.replace(temporary, target)
        except OSError as exc:
            raise ValueError("保存失败：{}".format(exc)) from exc
        self.path = target
        return target
