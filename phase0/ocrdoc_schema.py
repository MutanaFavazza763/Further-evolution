"""OCRDocument 的 JSON Schema 定义与校验（Phase 0 最小实现）。

数据契约来自 PROJECT_SPEC.md 第 5、6 节：
- 顶层：schema_version / meta / blocks
- block 类型：heading / paragraph / list / table / formula / image / handwritten
- 文字与公式通过 runs 在段落内混排
"""

import json
import re

from jsonschema import Draft7Validator

# ---------------------------------------------------------------- runs

TEXT_RUN = {
    "type": "object",
    "properties": {"kind": {"const": "text"}, "text": {"type": "string"}},
    "required": ["kind", "text"],
    "additionalProperties": True,
}

FORMULA_RUN = {
    "type": "object",
    "properties": {"kind": {"const": "formula"}, "latex": {"type": "string"}},
    "required": ["kind", "latex"],
    "additionalProperties": True,
}

RUN = {"oneOf": [TEXT_RUN, FORMULA_RUN]}
RUNS = {"type": "array", "items": RUN}

# ---------------------------------------------------------------- blocks

HEADING_BLOCK = {
    "type": "object",
    "properties": {"type": {"const": "heading"}, "text": {"type": "string"}},
    "required": ["type", "text"],
    "additionalProperties": True,
}

PARAGRAPH_BLOCK = {
    "type": "object",
    "properties": {"type": {"const": "paragraph"}, "runs": RUNS},
    "required": ["type", "runs"],
    "additionalProperties": True,
}

LIST_BLOCK = {
    "type": "object",
    "properties": {"type": {"const": "list"}, "items": {"type": "array", "items": RUNS}},
    "required": ["type", "items"],
    "additionalProperties": True,
}

TABLE_BLOCK = {
    "type": "object",
    "properties": {
        "type": {"const": "table"},
        "rows": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"runs": RUNS},
                    "additionalProperties": True,
                },
            },
        },
    },
    "required": ["type", "rows"],
    "additionalProperties": True,
}

FORMULA_BLOCK = {
    "type": "object",
    "properties": {"type": {"const": "formula"}, "latex": {"type": "string"}},
    "required": ["type", "latex"],
    "additionalProperties": True,
}

IMAGE_BLOCK = {
    "type": "object",
    "properties": {"type": {"const": "image"}},
    "required": ["type"],
    "additionalProperties": True,
}

HANDWRITTEN_BLOCK = {
    "type": "object",
    "properties": {"type": {"const": "handwritten"}, "runs": RUNS},
    "required": ["type", "runs"],
    "additionalProperties": True,
}

BLOCK = {
    "oneOf": [
        HEADING_BLOCK,
        PARAGRAPH_BLOCK,
        LIST_BLOCK,
        TABLE_BLOCK,
        FORMULA_BLOCK,
        IMAGE_BLOCK,
        HANDWRITTEN_BLOCK,
    ]
}

OCR_DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "meta": {"type": "object"},
        "blocks": {"type": "array", "items": BLOCK},
    },
    "required": ["blocks"],
    "additionalProperties": True,
}


def validate_ocr_document(data):
    """返回校验错误列表；空列表表示通过。"""
    validator = Draft7Validator(OCR_DOCUMENT_SCHEMA)
    return sorted(validator.iter_errors(data), key=lambda e: list(e.path))


def extract_json_from_text(text):
    """从模型输出中提取 JSON 对象，失败抛出 ValueError。"""
    text = (text or "").strip()

    # 1) 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3) 提取第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("JSON 解析失败: {}".format(exc))

    raise ValueError("未在模型输出中找到 JSON 对象")
