"""Phase 2 regression test。

验证：版面分析、内容分组、横向重排、16:9 渲染，
以及 handwritten / formula 不丢失。

用法（项目根）：
    python -m unittest phase2.tests.test_reflow -v
"""

import json
import sys
import unittest
from pathlib import Path

# 让测试能 import phase2（从项目根或直接运行）
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "phase0"))

from phase2.layout import analyze_layout
from phase2.ordering import order_groups
from phase2.reflow import choose_columns, reflow
from phase2.renderer import PageRenderer


FIXTURE = {
    "schema_version": "1.0",
    "blocks": [
        {"type": "heading", "level": 1, "text": "第一章 集合"},
        {
            "type": "paragraph",
            "runs": [
                {"kind": "text", "text": "集合 "},
                {"kind": "formula", "latex": "\\{x\\in\\mathbb{N}\\mid x<5\\}"},
            ],
        },
        {"type": "handwritten", "runs": [{"kind": "text", "text": "A"}]},
        {
            "type": "paragraph",
            "runs": [
                {"kind": "text", "text": "已知 "},
                {"kind": "formula", "latex": "x^2-4=0"},
            ],
        },
        {"type": "handwritten", "runs": [{"kind": "formula", "latex": "\\{-2,2\\}"}]},
    ],
}


def _block_types(blocks):
    return [b.get("type") for b in blocks]


class TestLayout(unittest.TestCase):
    def test_grouping_pairs_question_and_answer(self):
        layout = analyze_layout(FIXTURE["blocks"])
        # main 含 1 个 heading 组 + 2 个题目组
        self.assertEqual(len(layout.main), 3)
        # 题目组 = paragraph + 紧跟的 handwritten
        for g in layout.main[1:]:
            self.assertEqual(_block_types(g.blocks), ["paragraph", "handwritten"])

    def test_handwritten_and_formula_preserved(self):
        layout = analyze_layout(FIXTURE["blocks"])
        all_blocks = [b for g in layout.main for b in g.blocks] + layout.header + layout.footer
        types = _block_types(all_blocks)
        self.assertIn("handwritten", types)
        # formula run 保留（handwritten 组里有 formula run）
        formula_runs = 0
        for b in all_blocks:
            for r in b.get("runs", []):
                if r.get("kind") == "formula":
                    formula_runs += 1
        self.assertGreaterEqual(formula_runs, 2)


class TestReflow(unittest.TestCase):
    def test_choose_columns(self):
        self.assertEqual(choose_columns(2), 1)
        self.assertEqual(choose_columns(5), 2)
        self.assertEqual(choose_columns(10), 3)

    def test_reflow_columns_count(self):
        layout = analyze_layout(FIXTURE["blocks"])
        groups = order_groups(layout.main)
        cols = reflow(groups, columns=2)
        self.assertEqual(len(cols), 2)


class TestRender(unittest.TestCase):
    def test_render_16_9(self):
        layout = analyze_layout(FIXTURE["blocks"])
        groups = order_groups(layout.main)
        cols = reflow(groups)
        out = Path(__file__).resolve().parent / "_test_reflow.png"
        try:
            PageRenderer(width=1920, height=1080).render(layout, cols, str(out))
            from PIL import Image
            with Image.open(out) as img:
                self.assertEqual((img.width, img.height), (1920, 1080))
        finally:
            out.unlink(missing_ok=True)


class TestDocx(unittest.TestCase):
    def test_reflow_docx_landscape_16_9(self):
        from docx_builder import render_reflow
        layout = analyze_layout(FIXTURE["blocks"])
        groups = order_groups(layout.main)
        cols = reflow(groups, columns=2)
        out = Path(__file__).resolve().parent / "_test_reflow.docx"
        try:
            render_reflow(layout, cols, str(out))
            from docx import Document
            doc = Document(str(out))
            sec = doc.sections[0]
            self.assertEqual(str(sec.orientation), "LANDSCAPE (1)")
            self.assertAlmostEqual(sec.page_width.inches / sec.page_height.inches, 16 / 9, places=2)
        finally:
            out.unlink(missing_ok=True)

    def test_reflow_docx_has_omml(self):
        from docx_builder import render_reflow
        layout = analyze_layout(FIXTURE["blocks"])
        groups = order_groups(layout.main)
        cols = reflow(groups, columns=2)
        out = Path(__file__).resolve().parent / "_test_reflow.docx"
        try:
            render_reflow(layout, cols, str(out))
            import zipfile
            from lxml import etree
            with zipfile.ZipFile(str(out)) as z:
                xml = z.read("word/document.xml")
            M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
            omml = etree.fromstring(xml).findall(".//{{{}}}oMath".format(M))
            self.assertGreater(len(omml), 0)
        finally:
            out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
