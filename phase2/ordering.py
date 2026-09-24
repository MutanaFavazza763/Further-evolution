"""阅读顺序重建（Phase 3）。

无 bbox：保持 Phase 2 原顺序（向后兼容）。
有 bbox：基于归一化坐标重建阅读顺序——
  识别跨栏 block、单栏/双栏、按栏（左→右）且栏内自上而下排序。
"""

# 归一化坐标阈值
SPAN_WIDTH_THRESHOLD = 0.6   # width > 0.6 视为「跨栏」
COLUMN_GAP_THRESHOLD = 0.3   # cx 相邻最大间隙 > 0.3 视为分栏
COLUMN_SPLIT = 0.5           # cx < 0.5 左栏，>= 0.5 右栏


def _get_bbox(block):
    """返回有效 bbox dict；无效则返回 None。"""
    bbox = block.get("bbox")
    if not isinstance(bbox, dict):
        return None
    for k in ("x", "y", "width", "height"):
        if not isinstance(bbox.get(k), (int, float)):
            return None
    return bbox


def has_bbox(blocks):
    """所有 block 都有有效 bbox 才算 True。"""
    blocks = list(blocks or [])
    return bool(blocks) and all(_get_bbox(b) is not None for b in blocks)


def _cx(block):
    bbox = _get_bbox(block)
    return bbox["x"] + bbox["width"] / 2


def _cy(block):
    bbox = _get_bbox(block)
    return bbox["y"] + bbox["height"] / 2


def _is_spanning(block):
    return _get_bbox(block)["width"] > SPAN_WIDTH_THRESHOLD


def _detect_columns(in_col):
    """基于 cx 最大间隙判断栏数（1 或 2）。"""
    if len(in_col) < 2:
        return 1
    cxs = sorted(_cx(b) for b in in_col)
    max_gap = max(cxs[i] - cxs[i - 1] for i in range(1, len(cxs)))
    return 2 if max_gap > COLUMN_GAP_THRESHOLD else 1


def order_blocks_by_bbox(blocks):
    """基于 bbox 重建阅读顺序。

    单栏：整体按 y 自上而下排序。
    双栏：跨栏 block 按 y 排最前，其余左栏（按 y）+ 右栏（按 y）。
    """
    blocks = list(blocks)
    spanning = [b for b in blocks if _is_spanning(b)]
    in_col = [b for b in blocks if not _is_spanning(b)]

    if _detect_columns(in_col) <= 1:
        # 单栏：整体按 y 排序（稳定排序，同 y 保持原顺序）
        return sorted(blocks, key=_cy)

    left = sorted([b for b in in_col if _cx(b) < COLUMN_SPLIT], key=_cy)
    right = sorted([b for b in in_col if _cx(b) >= COLUMN_SPLIT], key=_cy)

    result = sorted(spanning, key=_cy)
    result.extend(left)
    result.extend(right)
    return result


def order_blocks(blocks):
    """公开入口：无 bbox 返回原顺序，有 bbox 重建阅读顺序。"""
    blocks = list(blocks or [])
    if not has_bbox(blocks):
        return blocks
    return order_blocks_by_bbox(blocks)


def order_groups(groups):
    """BlockGroup 列表保持 Phase 2 原顺序（分组后不再按坐标重排）。"""
    return list(groups)
