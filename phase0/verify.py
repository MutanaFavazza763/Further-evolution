"""Phase 0 最小验证入口：图片 -> AI -> OCRDocument JSON。

用法：
    python phase0/verify.py <图片路径>

环境变量（API Key 只从环境变量读取，禁止硬编码）：
    OCR2WORD_API_KEY      必填
    OCR2WORD_API_BASE     可选，默认 https://api.openai.com/v1
    OCR2WORD_MODEL        可选，默认 gpt-4o
    OCR2WORD_TIMEOUT      可选，默认 120 秒
    OCR2WORD_MAX_RETRIES  可选，默认 2
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from ocrdoc_schema import extract_json_from_text, validate_ocr_document
from provider import MIME_TYPES, OpenAICompatProvider, ProviderError

DEFAULT_OUTPUT_DIR = str(Path(__file__).resolve().parent / "output")


def _env_or_exit(name):
    value = os.environ.get(name)
    if not value:
        print("错误：未设置环境变量 {}".format(name))
        print("示例(PowerShell)：$env:{} = \"your-key\"".format(name))
        sys.exit(2)
    return value


def main():
    parser = argparse.ArgumentParser(description="图片 -> AI -> OCRDocument JSON")
    parser.add_argument("image", help="输入图片路径")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="结果输出目录")
    args = parser.parse_args()

    # 1) 环境变量（API Key 不硬编码）
    api_key = _env_or_exit("OCR2WORD_API_KEY")
    base_url = os.environ.get("OCR2WORD_API_BASE", "https://api.openai.com/v1")
    model = os.environ.get("OCR2WORD_MODEL", "gpt-4o")
    timeout = int(os.environ.get("OCR2WORD_TIMEOUT", "120"))
    max_retries = int(os.environ.get("OCR2WORD_MAX_RETRIES", "2"))

    # 2) 读图片
    image_path = Path(args.image)
    if not image_path.exists():
        print("错误：图片不存在：{}".format(image_path))
        sys.exit(2)
    mime = MIME_TYPES.get(image_path.suffix.lower())
    if mime is None:
        print("错误：不支持的图片格式：{}".format(image_path.suffix))
        sys.exit(2)
    image_bytes = image_path.read_bytes()

    sha256 = hashlib.sha256(image_bytes).hexdigest()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    stem = image_path.stem

    # 3) 调用 AI
    provider = OpenAICompatProvider(api_key, base_url, model, timeout, max_retries)
    print("正在调用模型 {} ...".format(model))
    try:
        raw_text = provider.recognize(image_bytes, mime)
    except ProviderError as exc:
        print("错误：{}".format(exc))
        sys.exit(3)

    # 4) 保存原始响应
    raw_path = out_dir / "{}__{}__raw.txt".format(stem, ts)
    raw_path.write_text(raw_text, encoding="utf-8")
    print("原始响应已保存：{}".format(raw_path))

    # 5) 解析 JSON
    try:
        data = extract_json_from_text(raw_text)
    except ValueError as exc:
        print("错误：AI 返回内容无法解析为 JSON：{}".format(exc))
        print("请查看原始响应：{}".format(raw_path))
        sys.exit(4)

    # 6) Schema 校验
    errors = validate_ocr_document(data)
    if errors:
        print("错误：OCRDocument 校验失败，共 {} 处：".format(len(errors)))
        for err in errors:
            path = "/".join(str(p) for p in err.path) or "(root)"
            print("  - {}: {}".format(path, err.message))
    else:
        print("OCRDocument 校验通过")

    # 7) 客户端注入 meta（AI 不负责填 sha256/路径等文件属性）
    data.setdefault("schema_version", "1.0")
    data["meta"] = {
        "source_path": str(image_path),
        "sha256": sha256,
        "language": "zh-CN",
        # width/height 需 Pillow 读取，Phase 1 再补
    }

    # 8) 保存解析后的 JSON
    json_path = out_dir / "{}__{}__result.json".format(stem, ts)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("解析后的 JSON 已保存：{}".format(json_path))

    # 9) 摘要
    blocks = data.get("blocks", [])
    counts = Counter(b.get("type", "?") for b in blocks if isinstance(b, dict))
    print("共 {} 个 block".format(len(blocks)))
    for block_type, count in counts.items():
        print("  {}: {}".format(block_type, count))

    if errors:
        sys.exit(5)


if __name__ == "__main__":
    main()
