"""版面理解：区域划分 + 内容分组（Phase 2 + Phase 3）。

- 无 bbox：沿用 Phase 2 启发式（基于 block 类型与顺序），向后兼容。
- 有 bbox：基于归一化坐标识别左右双栏，做双栏感知的题目+答案分组。
"""

from dataclasses import dataclass, field

# 归一化坐标阈值（与 ordering 保持一致）
SPAN_WIDTH_THRESHOLD = 0.6   # width > 0.6 视为「跨栏」
COLUMN_GAP_THRESHOLD = 0.15  # cx 相邻最大间隙 > 0.15 视为分栏
COLUMN_SPLIT = 0.5           # cx < 0.5 左栏，>= 0.5 右栏


@dataclass
class BlockGroup:
    """一组内容：通常是「题目 + 手写答案」。"""
    blocks: list = field(default_factory=list)

    def add(self, block):
        self.blocks.append(block)

    def text_preview(self):
        """组内纯文本预览（用于高度估算/调试）。"""
        parts = []
        for b in self.blocks:
            t = b.get("type")
            if t == "heading":
                parts.append(b.get("text", ""))
            elif t == "formula":
                parts.append(b.get("latex", ""))
            elif t in ("paragraph", "handwritten"):
                for r in b.get("runs", []):
                    parts.append(r.get("text", "") or r.get("latex", ""))
            elif t == "list":
                for item in b.get("items", []):
                    for r in item:
                        parts.append(r.get("text", "") or r.get("latex", ""))
            elif t == "image":
                parts.append("[图片]")
        return "".join(parts)

    def estimate_height(self):
        """粗略估算渲染高度（用于分列均衡）。"""
        text = self.text_preview()
        lines = max(1, len(text) // 30 + 1)
        return lines * 44 + len(self.blocks) * 12


@dataclass
class PageLayout:
    header: list = field(default_factory=list)
    main: list = field(default_factory=list)   # list[BlockGroup]
    footer: list = field(default_factory=list)
    spanning: list = field(default_factory=list)  # list[BlockGroup]（全宽标题，双栏时）


# ---------------------------------------------------------------- bbox helpers

def _get_bbox(block):
    bbox = block.get("bbox")
    if not isinstance(bbox, dict):
        return None
    for k in ("x", "y", "width", "height"):
        if not isinstance(bbox.get(k), (int, float)):
            return None
    return bbox


def _has_bbox(blocks):
    return bool(blocks) and all(_get_bbox(b) is not None for b in blocks)


def _cx(block):
    b = _get_bbox(block)
    return b["x"] + b["width"] / 2


def _top_y(block):
    """返回 block 顶部 y，用于保持高块与其起始内容的阅读顺序。"""
    b = _get_bbox(block)
    return b["y"]


def _is_spanning(block):
    return _get_bbox(block)["width"] > SPAN_WIDTH_THRESHOLD


def _detect_columns(in_col):
    if len(in_col) < 2:
        return 1
    cxs = sorted(_cx(b) for b in in_col)
    max_gap = max(cxs[i] - cxs[i - 1] for i in range(1, len(cxs)))
    return 2 if max_gap > COLUMN_GAP_THRESHOLD else 1


# ---------------------------------------------------------------- analyze

def analyze_layout(blocks):
    """划分 header / main / footer，并对 main 做题目+答案分组。"""
    blocks = list(blocks or [])
    if not blocks:
        return PageLayout()

    # 第一个 level<=2 的 heading 作为 main 起点；无此类 heading 时全部归 main
    main_start = 0
    for i, b in enumerate(blocks):
        if b.get("type") == "heading" and int(b.get("level", 9)) <= 2:
            main_start = i
            break

    header = blocks[:main_start]
    main_blocks = blocks[main_start:]

    # footer：结尾与章节标题相同的重复 heading（两种模式共用）
    footer = []
    first_heading_text = None
    for b in main_blocks:
        if b.get("type") == "heading":
            first_heading_text = b.get("text", "")
            break
    tail = []
    while main_blocks and main_blocks[-1].get("type") == "heading":
        b = main_blocks[-1]
        if first_heading_text and b.get("text", "") == first_heading_text:
            tail.append(main_blocks.pop())
        else:
            break
    footer = list(reversed(tail))

    # main 分组：有 bbox 分离 spanning，无 bbox 用现有启发式
    if _has_bbox(blocks):
        spanning_groups, main_groups = _split_spanning(main_blocks)
    else:
        spanning_groups, main_groups = [], _group_blocks(main_blocks)

    return PageLayout(header=header, main=main_groups, footer=footer, spanning=spanning_groups)


def _group_blocks(blocks):
    """paragraph/heading 等开始新组，handwritten/image 追加到当前组。"""
    groups = []
    current = None
    for block in blocks:
        t = block.get("type")
        if t in ("paragraph", "heading", "list", "table", "formula"):
            current = BlockGroup(blocks=[block])
            groups.append(current)
        else:  # handwritten / image
            if current is None:
                current = BlockGroup(blocks=[block])
                groups.append(current)
            else:
                current.add(block)
    return groups


def _split_spanning(main_blocks):
    """分离跨栏标题和栏内容，返回 (spanning_groups, column_groups)。

    只有确认双栏时，才把 _is_spanning 识别的 heading 分离到 spanning。
    单栏时返回 ([], _group_blocks(main_blocks))，保持原有分组行为。
    """
    spanning_blocks = [b for b in main_blocks if _is_spanning(b)]
    in_col = [b for b in main_blocks if not _is_spanning(b)]

    if _detect_columns(in_col) <= 1:
        # 单栏：无跨栏概念，全部作为栏内容
        return [], _group_blocks(main_blocks)

    # 双栏：spanning 按 y 排序单独成组，栏内容按左栏→右栏分组
    spanning_groups = [BlockGroup(blocks=[b]) for b in sorted(spanning_blocks, key=_top_y)]
    left = sorted([b for b in in_col if _cx(b) < COLUMN_SPLIT], key=_top_y)
    right = sorted([b for b in in_col if _cx(b) >= COLUMN_SPLIT], key=_top_y)
    column_groups = _group_blocks(left) + _group_blocks(right)
    return spanning_groups, column_groups
