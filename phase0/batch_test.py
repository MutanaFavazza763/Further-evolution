"""Phase 0.5 批量 OCR 压力测试脚本（独立测试工具，非软件功能）。

遍历测试图片目录，逐张调用现有 provider 与 schema，
保存 raw/result 到 output/<图片名>/，最后打印汇总。

不改动 verify.py / provider.py / ocrdoc_schema.py。

用法：
    python phase0/batch_test.py [--input-dir ...] [--output-dir ...]
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

from ocrdoc_schema import extract_json_from_text, validate_ocr_document
from provider import MIME_TYPES, OpenAICompatProvider, ProviderError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

DEFAULT_INPUT_DIR = str(Path(__file__).resolve().parent / "test_images")
DEFAULT_OUTPUT_DIR = str(Path(__file__).resolve().parent / "output")


def process_one(provider, image_path, out_dir):
    """处理单张图片，返回一个汇总 dict。"""
    entry = {
        "image": image_path.name,
        "status": "ok",
        "schema_errors": [],
        "block_types": {},
        "error_message": "",
    }
    mime = MIME_TYPES.get(image_path.suffix.lower())

    try:
        image_bytes = image_path.read_bytes()
    except OSError as exc:
        entry["status"] = "read_error"
        entry["error_message"] = str(exc)
        return entry

    sha256 = hashlib.sha256(image_bytes).hexdigest()
    sub = out_dir / image_path.stem
    sub.mkdir(parents=True, exist_ok=True)

    try:
        raw_text = provider.recognize(image_bytes, mime)
    except ProviderError as exc:
        entry["status"] = "api_error"
        entry["error_message"] = str(exc)
        return entry

    (sub / "raw.txt").write_text(raw_text, encoding="utf-8")

    try:
        data = extract_json_from_text(raw_text)
    except ValueError as exc:
        entry["status"] = "parse_error"
        entry["error_message"] = str(exc)
        return entry

    errors = validate_ocr_document(data)
    entry["schema_errors"] = [
        {"path": "/".join(str(p) for p in e.path) or "(root)", "message": e.message}
        for e in errors
    ]
    if errors:
        entry["status"] = "schema_error"

    data.setdefault("schema_version", "1.0")
    data["meta"] = {
        "source_path": str(image_path),
        "sha256": sha256,
        "language": "zh-CN",
    }
    (sub / "result.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    blocks = data.get("blocks", [])
    entry["block_types"] = dict(
        Counter(b.get("type", "?") for b in blocks if isinstance(b, dict))
    )
    return entry


def main():
    parser = argparse.ArgumentParser(description="批量 OCR 压力测试")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    api_key = os.environ.get("OCR2WORD_API_KEY")
    if not api_key:
        print("错误：未设置环境变量 OCR2WORD_API_KEY")
        sys.exit(2)
    base_url = os.environ.get("OCR2WORD_API_BASE", "https://api.deepseek.com")
    model = os.environ.get("OCR2WORD_MODEL", "deepseek-flash")
    timeout = int(os.environ.get("OCR2WORD_TIMEOUT", "120"))
    max_retries = int(os.environ.get("OCR2WORD_MAX_RETRIES", "2"))

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print("错误：图片目录不存在：{}".format(input_dir))
        sys.exit(2)

    images = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        print("错误：目录 {} 下没有图片".format(input_dir))
        sys.exit(2)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    provider = OpenAICompatProvider(api_key, base_url, model, timeout, max_retries)
    summary = []

    print("共 {} 张图片，模型 {}".format(len(images), model))
    for idx, image_path in enumerate(images, 1):
        print("\n[{} / {}] {}".format(idx, len(images), image_path.name))
        entry = process_one(provider, image_path, out_dir)
        summary.append(entry)
        if entry["status"] == "ok":
            print("  -> 校验通过，blocks: {}".format(entry["block_types"]))
        else:
            print("  -> {}: {}".format(entry["status"], entry["error_message"]))

    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    ok = sum(1 for e in summary if e["status"] == "ok")
    print("通过 {} / {} 张".format(ok, len(summary)))
    for e in summary:
        print("  [{}] {} — blocks: {}".format(e["status"], e["image"], e["block_types"]))
    print("\n结果已保存到：{}".format(out_dir))


if __name__ == "__main__":
    main()
