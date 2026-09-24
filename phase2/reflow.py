"""横向重排：把竖向内容流重排成多列（适配 16:9）。

根据内容组数量决定列数，并用高度估算做贪心分配，让各列尽量等高。
"""


def choose_columns(group_count):
    """根据内容组数量决定列数。"""
    if group_count <= 3:
        return 1
    if group_count <= 7:
        return 2
    return 3


def reflow(groups, columns=None):
    """把 groups 分配到 columns 列。

    返回 list[list[BlockGroup]]，每列是一个按顺序排列的 groups 列表。
    """
    groups = list(groups)
    if not groups:
        return []
    if columns is None:
        columns = choose_columns(len(groups))
    columns = max(1, min(columns, len(groups)))

    col_heights = [0] * columns
    result = [[] for _ in range(columns)]
    for g in groups:
        idx = col_heights.index(min(col_heights))
        result[idx].append(g)
        col_heights[idx] += g.estimate_height()

    return result
