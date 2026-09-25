"""Phase 3 layout 单元测试：bbox 版 header/main/footer + 双栏分组。"""

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from phase2.layout import analyze_layout
from phase2.ordering import order_blocks

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _group_types(layout):
    return [[b.get("type") for b in g.blocks] for g in layout.main]


def _labels_of(groups):
    result = []
    for g in groups:
        b = g.blocks[0]
        t = b.get("type")
        if t == "heading":
            result.append(b.get("text", ""))
        elif t in ("paragraph", "handwritten"):
            runs = b.get("runs", [])
            result.append(runs[0].get("text", "") if runs else "")
    return result


class TestLayoutBbox(unittest.TestCase):
    def test_no_bbox_uses_heuristic(self):
        blocks = _load("no_bbox.json")["blocks"]
        layout = analyze_layout(blocks)
        # 标题组 + (题目一+A) + 题目二 = 3 组
        self.assertEqual(len(layout.main), 3)

    def test_single_column_pairs_question_answer(self):
        blocks = _load("single_column_bbox.json")["blocks"]
        layout = analyze_layout(order_blocks(blocks))
        self.assertEqual(_group_types(layout), [
            ["heading"],
            ["paragraph", "handwritten"],
            ["paragraph", "handwritten"],
            ["paragraph"],
        ])

    def test_double_column_separates_columns(self):
        blocks = _load("double_column_bbox.json")["blocks"]
        layout = analyze_layout(order_blocks(blocks))
        # 标题在 spanning（全宽），main 只剩左右栏内容
        self.assertEqual(_labels_of(layout.spanning), ["标题"])
        self.assertEqual(_labels_of(layout.main), ["1", "2", "3", "4", "5"])

    def test_spanning_title_separates_columns(self):
        blocks = _load("spanning_title_bbox.json")["blocks"]
        layout = analyze_layout(order_blocks(blocks))
        self.assertEqual(_labels_of(layout.spanning), ["章节标题"])
        self.assertEqual(
            _labels_of(layout.main),
            ["左1", "左2", "左3", "右1", "右2", "右3"],
        )

    def test_realistic_double_column_separates(self):
        blocks = _load("realistic_double_column_bbox.json")["blocks"]
        layout = analyze_layout(order_blocks(blocks))
        self.assertEqual(_labels_of(layout.spanning), [])
        self.assertEqual(
            _labels_of(layout.main),
            ["10", "11", "12", "13", "14", "15"],
        )

    def test_single_column_scattered_not_split(self):
        blocks = _load("single_column_scattered_bbox.json")["blocks"]
        layout = analyze_layout(order_blocks(blocks))
        self.assertEqual(_labels_of(layout.spanning), [])
        self.assertEqual(_labels_of(layout.main), ["1", "2", "3", "4"])

    def test_tall_block_remains_with_its_question(self):
        blocks = [
            {"type": "paragraph", "runs": [{"kind": "text", "text": "左栏"}],
             "bbox": {"x": 0.05, "y": 0.20, "width": 0.35, "height": 0.05}},
            {"type": "paragraph", "runs": [{"kind": "text", "text": "题15"}],
             "bbox": {"x": 0.55, "y": 0.239, "width": 0.35, "height": 0.125}},
            {"type": "handwritten", "runs": [{"kind": "text", "text": "题15答案"}],
             "bbox": {"x": 0.55, "y": 0.368, "width": 0.35, "height": 0.53}},
            {"type": "image", "bbox": {"x": 0.90, "y": 0.412, "width": 0.08, "height": 0.068}},
            {"type": "paragraph", "runs": [{"kind": "text", "text": "错题本"}],
             "bbox": {"x": 0.90, "y": 0.481, "width": 0.08, "height": 0.018}},
        ]
        layout = analyze_layout(order_blocks(blocks))
        self.assertEqual(
            _group_types(layout),
            [["paragraph"], ["paragraph", "handwritten", "image"], ["paragraph"]],
        )
        self.assertEqual(_labels_of(layout.main), ["左栏", "题15", "错题本"])


if __name__ == "__main__":
    unittest.main()
