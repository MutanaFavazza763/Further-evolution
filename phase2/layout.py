"""版面理解：区域划分 + 内容分组（Phase 2 MVP）。

基于 block 类型与顺序做启发式分析，不依赖坐标（当前 schema 无 bbox）。

输入：OCRDocument 的 blocks 列表
输出：PageLayout（header / main_groups / footer）
"""

from dataclasses import dataclass, field


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


def analyze_layout(blocks):
    """划分 header / main / footer，并对 main 做题目+答案分组。"""
    blocks = list(blocks or [])
    if not blocks:
        return PageLayout()

    # 第一个 level<=2 的 heading 作为 main 起点
    main_start = len(blocks)
    for i, b in enumerate(blocks):
        if b.get("type") == "heading" and int(b.get("level", 9)) <= 2:
            main_start = i
            break

    header = blocks[:main_start]
    main_blocks = blocks[main_start:]

    # footer：结尾与章节标题相同的重复 heading
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

    return PageLayout(header=header, main=_group_blocks(main_blocks), footer=footer)


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
