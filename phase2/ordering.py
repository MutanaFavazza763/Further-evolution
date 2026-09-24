"""阅读顺序抽象（Phase 2 MVP）。

当前 schema 无坐标，AI 已按自上而下输出 blocks，
因此 MVP 直接返回原顺序。预留 bbox 排序接口，未来可在此实现
「左栏读完读右栏」的真实阅读顺序。
"""


def order_groups(groups):
    """返回按阅读顺序排列的 BlockGroup 列表。MVP 返回原顺序。"""
    return list(groups)


def order_blocks(blocks):
    """返回按阅读顺序排列的 block 列表。MVP 返回原顺序。"""
    return list(blocks)
