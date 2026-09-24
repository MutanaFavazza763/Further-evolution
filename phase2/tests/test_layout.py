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


def _group_labels(layout):
    result = []
    for g in layout.main:
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
        self.assertEqual(_group_labels(layout), ["标题", "1", "2", "3", "4", "5"])

    def test_spanning_title_separates_columns(self):
        blocks = _load("spanning_title_bbox.json")["blocks"]
        layout = analyze_layout(order_blocks(blocks))
        self.assertEqual(
            _group_labels(layout),
            ["章节标题", "左1", "左2", "左3", "右1", "右2", "右3"],
        )


if __name__ == "__main__":
    unittest.main()
