"""Phase 0.6 CLI：读一个 OCRDocument result.json -> 生成 .docx。

用法：
    python phase0/verify_docx.py <result.json> [--output 输出.docx]
"""

import argparse
import json
import sys
from pathlib import Path

from docx_builder import render_document


def main():
    parser = argparse.ArgumentParser(description="OCRDocument JSON -> .docx")
    parser.add_argument("result_json", help="OCRDocument result.json 路径")
    parser.add_argument("--output", default=None, help="输出 .docx 路径（默认同名）")
    args = parser.parse_args()

    path = Path(args.result_json)
    if not path.exists():
        print("错误：文件不存在：{}".format(path))
        sys.exit(2)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print("错误：JSON 解析失败：{}".format(exc))
        sys.exit(3)

    output = args.output or str(path.with_suffix(".docx"))
    try:
        render_document(data, output)
    except Exception as exc:
        print("错误：生成 docx 失败：{}".format(exc))
        sys.exit(4)

    print("已生成：{}".format(output))


if __name__ == "__main__":
    main()
