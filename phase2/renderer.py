"""最终渲染：输出 16:9 PNG（Phase 2 MVP）。

- 中文用 Pillow 绘制
- 数学公式用 matplotlib mathtext 渲染成透明图后贴回，保留 LaTeX
- 手写内容用蓝色区分，保留原 block
- image block 渲染为占位框（暂不裁剪原图）
"""

import re
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont


def _normalize_latex(latex):
    """把 matplotlib mathtext 不支持的命令映射到支持的。"""
    latex = re.sub(r"\\le(?![a-zA-Z])", r"\\leq", latex)
    latex = re.sub(r"\\ge(?![a-zA-Z])", r"\\geq", latex)
    return latex


class FormulaRenderer:
    """用 matplotlib mathtext 把 LaTeX 渲染成透明 PNG。"""

    def __init__(self):
        matplotlib.rcParams["mathtext.fontset"] = "stix"

    def render(self, latex, fontsize=22):
        latex = _normalize_latex(latex)
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0.5, 0.5, "${}$".format(latex), fontsize=fontsize,
                 ha="center", va="center")
        buf = BytesIO()
        try:
            fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                        pad_inches=0.02, transparent=True)
            buf.seek(0)
            return Image.open(buf).convert("RGBA")
        finally:
            plt.close(fig)


def _find_cjk_font():
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


class PageRenderer:
    def __init__(self, width=1920, height=1080, margin=48):
        self.width = width
        self.height = height
        self.margin = margin
        self.formula = FormulaRenderer()
        self.font_path = _find_cjk_font()
        self.img = None
        self.draw = None

    def _font(self, size):
        if self.font_path and self.font_path.lower().endswith(".ttc"):
            return ImageFont.truetype(self.font_path, size, index=0)
        if self.font_path:
            return ImageFont.truetype(self.font_path, size)
        return ImageFont.load_default()

    def _line_height(self, size):
        return int(size * 1.4)

    # ---------------------------------------------------------------- 顶层

    def render(self, layout, columns, output_path):
        self.img = Image.new("RGB", (self.width, self.height), "white")
        self.draw = ImageDraw.Draw(self.img)

        content_w = self.width - 2 * self.margin
        y = self.margin

        # header（顶部）
        if layout.header:
            y = self._draw_blocks(layout.header, self.margin, y, self.margin + content_w) + 20

        # main 多列
        if columns:
            n = len(columns)
            col_gap = 28
            col_w = (content_w - col_gap * (n - 1)) // n
            x = self.margin
            for col_groups in columns:
                self._draw_column(col_groups, x, y, col_w, self.height - self.margin)
                x += col_w + col_gap

        # footer（底部）
        if layout.footer:
            fy = self.height - self.margin - 50
            self._draw_blocks(layout.footer, self.margin, fy, self.width - self.margin)

        self.img.save(output_path)
        return output_path

    def _draw_blocks(self, blocks, x0, y, max_x):
        cur = y
        for b in blocks:
            cur = self._draw_block(b, x0, cur, max_x) + 10
        return cur

    def _draw_column(self, groups, x0, y, col_w, max_y):
        cur = y
        max_x = x0 + col_w
        for g in groups:
            for b in g.blocks:
                cur = self._draw_block(b, x0, cur, max_x) + 8
        return cur

    # ---------------------------------------------------------------- block

    def _draw_block(self, block, x0, y, max_x):
        t = block.get("type")
        if t == "heading":
            level = int(block.get("level", 1))
            size = {1: 40, 2: 34, 3: 28}.get(level, 28)
            return self._draw_wrapped_text(block.get("text", ""), x0, y, max_x,
                                           self._font(size), "#1a1a1a", size)
        if t == "formula":
            return self._draw_runs([{"kind": "formula", "latex": block.get("latex", "")}],
                                   x0, y, max_x, size=24, color="#000000")
        if t in ("paragraph", "handwritten"):
            size = 24 if t == "handwritten" else 25
            color = "#0050c8" if t == "handwritten" else "#000000"
            return self._draw_runs(block.get("runs", []), x0, y, max_x, size=size, color=color)
        if t == "list":
            return self._draw_list(block, x0, y, max_x)
        if t == "image":
            return self._draw_image_placeholder(x0, y, max_x)
        return y

    # ---------------------------------------------------------------- runs 混排

    def _draw_runs(self, runs, x0, y, max_x, size=25, color="#000000"):
        font = self._font(size)
        x = x0
        cur_y = y
        cur_h = self._line_height(size)

        for run in runs or []:
            kind = run.get("kind")
            if kind == "text":
                text = run.get("text", "")
                if not text:
                    continue
                for ch in text:
                    w = self.draw.textlength(ch, font=font)
                    if x + w > max_x and x > x0:
                        cur_y += cur_h + 4
                        x = x0
                    self.draw.text((x, cur_y), ch, font=font, fill=color)
                    x += w
            elif kind == "formula":
                latex = run.get("latex", "")
                if not latex:
                    continue
                try:
                    fimg = self.formula.render(latex, fontsize=size)
                except Exception:
                    # 降级为文本
                    text = latex
                    for ch in text:
                        w = self.draw.textlength(ch, font=font)
                        if x + w > max_x and x > x0:
                            cur_y += cur_h + 4
                            x = x0
                        self.draw.text((x, cur_y), ch, font=font, fill=color)
                        x += w
                    continue
                fw, fh = fimg.size
                if x + fw > max_x and x > x0:
                    cur_y += cur_h + 4
                    x = x0
                fy = cur_y + (cur_h - fh) // 2 if fh < cur_h else cur_y
                self.img.paste(fimg, (int(x), int(fy)), fimg)
                x += fw
        return cur_y + cur_h

    def _draw_wrapped_text(self, text, x0, y, max_x, font, color, size):
        x = x0
        cur_y = y
        cur_h = self._line_height(size)
        for ch in text:
            w = self.draw.textlength(ch, font=font)
            if x + w > max_x and x > x0:
                cur_y += cur_h + 2
                x = x0
            self.draw.text((x, cur_y), ch, font=font, fill=color)
            x += w
        return cur_y + cur_h

    def _draw_list(self, block, x0, y, max_x):
        ordered = block.get("ordered", False)
        cur = y
        for idx, item in enumerate(block.get("items", []), 1):
            prefix = "{}. ".format(idx) if ordered else "\u2022 "
            pf = self._font(23)
            self.draw.text((x0, cur), prefix, font=pf, fill="#000000")
            pw = self.draw.textlength(prefix, font=pf)
            cur = self._draw_runs(item, x0 + int(pw), cur, max_x, size=23, color="#000000")
        return cur

    def _draw_image_placeholder(self, x0, y, max_x):
        w = min(360, max_x - x0)
        h = 140
        self.draw.rectangle([x0, y, x0 + w, y + h], outline="#999999", width=2)
        label = "[图片]"
        lf = self._font(22)
        lw = self.draw.textlength(label, font=lf)
        self.draw.text((x0 + (w - lw) / 2, y + (h - 30) / 2), label, font=lf, fill="#888888")
        return y + h
