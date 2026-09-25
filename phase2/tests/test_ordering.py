"""Phase 3 ordering 单元测试：基于 bbox 的阅读顺序重建。"""

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from phase2.ordering import has_bbox, order_blocks

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _label(block):
    t = block.get("type")
    if t == "heading":
        return block.get("text", "")
    if t in ("paragraph", "handwritten"):
        runs = block.get("runs", [])
        if runs:
            return runs[0].get("text", "") or runs[0].get("latex", "")
    return ""


def _labels(blocks):
    return [_label(b) for b in blocks]


class TestOrdering(unittest.TestCase):
    def test_no_bbox_keeps_original_order(self):
        blocks = _load("no_bbox.json")["blocks"]
        self.assertFalse(has_bbox(blocks))
        self.assertEqual(_labels(order_blocks(blocks)), _labels(blocks))

    def test_single_column_keeps_order(self):
        blocks = _load("single_column_bbox.json")["blocks"]
        self.assertTrue(has_bbox(blocks))
        self.assertEqual(_labels(order_blocks(blocks)), _labels(blocks))

    def test_double_column_reorders(self):
        blocks = _load("double_column_bbox.json")["blocks"]
        self.assertEqual(
            _labels(order_blocks(blocks)),
            ["标题", "1", "2", "3", "4", "5"],
        )

    def test_spanning_title_reorders(self):
        blocks = _load("spanning_title_bbox.json")["blocks"]
        self.assertEqual(
            _labels(order_blocks(blocks)),
            ["章节标题", "左1", "左2", "左3", "右1", "右2", "右3"],
        )

    def test_realistic_double_column_reorders(self):
        blocks = _load("realistic_double_column_bbox.json")["blocks"]
        self.assertEqual(
            _labels(order_blocks(blocks)),
            ["10", "11", "12", "13", "14", "15"],
        )

    def test_single_column_scattered_not_split(self):
        blocks = _load("single_column_scattered_bbox.json")["blocks"]
        self.assertEqual(_labels(order_blocks(blocks)), ["1", "2", "3", "4"])

    def test_tall_block_uses_top_edge_for_vertical_order(self):
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
        self.assertEqual(
            _labels(order_blocks(blocks)),
            ["左栏", "题15", "题15答案", "", "错题本"],
        )


if __name__ == "__main__":
    unittest.main()
