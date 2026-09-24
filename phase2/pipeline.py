"""Phase 2 流水线：JSON → layout → ordering → reflow → 横向 16:9 DOCX。

用法：
    python phase2/pipeline.py <OCRDocument.json> [--output xxx.docx]
                                  [--columns N] [--preview xxx.png]

主输出是横向 16:9 的可编辑 DOCX；--preview 可选生成 PNG 调试预览。
"""

import argparse
import json
import sys
from pathlib import Path

# 复用 phase0 的 schema 校验 + DOCX 渲染
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "phase0"))
from docx_builder import render_reflow
from ocrdoc_schema import validate_ocr_document

from layout import analyze_layout
from ordering import order_groups
from reflow import choose_columns, reflow
from renderer import PageRenderer


def build_layout(json_path, columns=None):
    """读取 JSON 并做版面分析 + 横向重排，返回 (layout, columns_list)。"""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    errors = validate_ocr_document(data)
    if errors:
        raise ValueError("Schema 校验失败: {}".format(errors[0].message))

    layout = analyze_layout(data.get("blocks", []))
    groups = order_groups(layout.main)

    if columns is None:
        columns = choose_columns(len(groups))
    columns_list = reflow(groups, columns=columns)

    return layout, columns_list


def reflow_docx(json_path, output_path, xsl_path=None):
    """生成横向 16:9 DOCX（主输出）。返回 (output_path, stats)。"""
    layout, columns_list = build_layout(json_path)
    render_reflow(layout, columns_list, str(output_path), xsl_path)

    stats = {
        "header_blocks": len(layout.header),
        "footer_blocks": len(layout.footer),
        "groups": sum(len(c) for c in columns_list),
        "columns": len(columns_list),
        "output": str(output_path),
    }
    return output_path, stats


def reflow_preview(json_path, output_path, width=1920, height=1080):
    """生成 PNG 调试预览（可选）。"""
    layout, columns_list = build_layout(json_path)
    PageRenderer(width=width, height=height).render(layout, columns_list, str(output_path))
    return output_path


def main():
    parser = argparse.ArgumentParser(description="OCRDocument JSON -> 横向 16:9 DOCX")
    parser.add_argument("json_path", help="OCRDocument JSON 路径")
    parser.add_argument("--output", default=None, help="输出 DOCX 路径（默认 <名>_reflow.docx）")
    parser.add_argument("--columns", type=int, default=None, help="列数（默认自动）")
    parser.add_argument("--preview", default=None, help="可选 PNG 预览路径")
    args = parser.parse_args()

    p = Path(args.json_path)
    output = args.output or str(p.with_name(p.stem + "_reflow.docx"))

    try:
        out, stats = reflow_docx(p, output)
    except Exception as exc:
        print("错误：{}".format(exc))
        sys.exit(1)

    print("输出 DOCX：{}".format(out))
    print("统计：header={header_blocks}, footer={footer_blocks}, "
          "groups={groups}, columns={columns}".format(**stats))

    if args.preview:
        try:
            reflow_preview(p, args.preview)
            print("预览 PNG：{}".format(args.preview))
        except Exception as exc:
            print("预览生成失败（不影响 DOCX）：{}".format(exc))


if __name__ == "__main__":
    main()
