"""Phase 1 监控入口：轮询 input/ 目录，自动 OCR -> JSON -> DOCX。

用法：
    python phase0/main.py [--input-dir input] [--output-dir output] ...

环境变量（API Key 只从环境变量读取，禁止硬编码）：
    OCR2WORD_API_KEY      必填
    OCR2WORD_API_BASE     可选，默认 https://api.deepseek.com
    OCR2WORD_MODEL        可选，默认 deepseek-flash
    OCR2WORD_TIMEOUT      可选，默认 120 秒
    OCR2WORD_MAX_RETRIES  可选，默认 2
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from pipeline import Pipeline, ProcessRecordStore, is_file_stable
from provider import MIME_TYPES, OpenAICompatProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXTS = set(MIME_TYPES.keys())

logger = logging.getLogger("main")


def setup_logging(logs_dir):
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "pipeline.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def scan_once(input_dir, pipeline):
    """扫描一次 input/，对稳定且未处理的图片调用流水线。"""
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if not is_file_stable(path):
            continue
        status = pipeline.process_image(path)
        if status in ("success", "failed"):
            logger.info("文件 %s 处理结果：%s", path.name, status)


def main():
    parser = argparse.ArgumentParser(description="OCR -> DOCX 自动监控")
    parser.add_argument("--input-dir", default=str(PROJECT_ROOT / "input"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "output"))
    parser.add_argument("--failed-dir", default=str(PROJECT_ROOT / "failed"))
    parser.add_argument("--logs-dir", default=str(PROJECT_ROOT / "logs"))
    parser.add_argument("--record-file", default=str(PROJECT_ROOT / "processed.json"))
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    setup_logging(args.logs_dir)

    api_key = os.environ.get("OCR2WORD_API_KEY")
    if not api_key:
        logger.error("未设置环境变量 OCR2WORD_API_KEY")
        logger.error("示例(PowerShell)：$env:OCR2WORD_API_KEY = \"your-key\"")
        sys.exit(2)
    base_url = os.environ.get("OCR2WORD_API_BASE", "https://api.deepseek.com")
    model = os.environ.get("OCR2WORD_MODEL", "deepseek-flash")
    timeout = int(os.environ.get("OCR2WORD_TIMEOUT", "120"))
    max_retries = int(os.environ.get("OCR2WORD_MAX_RETRIES", "2"))

    input_dir = Path(args.input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    provider = OpenAICompatProvider(api_key, base_url, model, timeout, max_retries)
    store = ProcessRecordStore(args.record_file)
    pipeline = Pipeline(provider, input_dir, args.output_dir, args.failed_dir, store)

    logger.info(
        "监控启动：input=%s, interval=%.1fs, model=%s",
        input_dir, args.interval, model,
    )
    logger.info("将图片放入 %s 即会自动处理（Ctrl+C 退出）", input_dir)

    try:
        while True:
            scan_once(input_dir, pipeline)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("监控已停止")


if __name__ == "__main__":
    main()
