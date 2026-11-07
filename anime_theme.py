# -*- coding: utf-8 -*-
"""Audio2Phira · 二次元主题层  MUSE POP / 喵斯波普风

参考《Muse Dash》的视觉语言：
  高饱和糖果霓虹（品红 / 亮青 / 亮黄 / 柠檬绿）× 粗黑描边贴纸块
  × 斜条纹与半调网点 × 描边粗体字 × 小恶魔系角色 × 高速粒子。

本模块只负责“画风”，共四件事：
  1. 调色板与字体（C / UI / DISPLAY / BLACK / MONO / font）
  2. ttk 样式（apply：按钮、标签页、输入框、树形表、进度条、滚动条，全部粗描边）
  3. 头图编排（AnimeHeader：斜条纹、网点、描边标题、锯齿边、流动粒子）
  4. 小恶魔角色绘制与眨眼（AnimeHeader 内部）

生成逻辑、任务调度、参数校验全部在 desktop_app / desktop_worker 中，
本文件不 import 任何业务模块，也不改写任何业务方法，只被他们调用。
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

__all__ = [
    'C', 'UI', 'DISPLAY', 'BLACK', 'MONO', 'CJK', 'font', 'mix',
    'round_rect', 'vertical_gradient', 'skew_band', 'halftone',
    'outlined_text', 'apply', 'AnimeHeader',
]


# ──────────────────────────────────────────────────────────────────────────
# 调色板：糖晶品红 / 电光青 / 柠檬黄 / 毒紫，全部压在深紫黑上
# ──────────────────────────────────────────────────────────────────────────
class C:
    VOID = '#0b0414'          # 最底层
    BG = '#170a28'            # 主背景
    BG_ALT = '#22103c'
    CARD = '#2a1250'          # 卡片
    INK = '#0d0518'           # 粗描边用的近黑紫

    PINK = '#ff3d9a'          # 主强调
    PINK_HI = '#ff9ad0'
    PINK_SOFT = '#ffc9e6'
    CYAN = '#22e0e6'
    YELLOW = '#ffe14d'
    LIME = '#a8ff3e'
    PURPLE = '#9b5cff'
    PURPLE_DEEP = '#6a2fd0'
    ORANGE = '#ff8a3d'

    INPUT = '#1e0d36'
    TEXT = '#ffffff'
    TEXT_DIM = '#cbb9ec'
    TEXT_FAINT = '#8d78ab'

    LOG_BG = '#100620'
    LOG_FG = '#7ff5ff'

    HEAD_1 = '#170a28'
    HEAD_2 = '#3b1166'
    HEAD_3 = '#8a1a92'
    HEAD_4 = '#ff3d9a'


# 字体族：apply() 时按本机可用字体自动替换
UI = 'Microsoft YaHei UI'
DISPLAY = 'Segoe UI Black'
BLACK = 'Microsoft YaHei UI'
MONO = 'Consolas'
CJK = 'Microsoft YaHei UI'


def pick_fonts(root=None):
    """按优先级挑本机存在的字体：正文用雅黑，标题/分组用超粗黑体。"""
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()

    def first(*names):
        for name in names:
            if name in families:
                return name
        return names[-1]

    ui = first('Microsoft YaHei UI', 'DengXian', 'MiSans', 'Noto Sans SC', 'SimHei')
    display = first('Segoe UI Black', 'Noto Sans SC Black', 'MiSans', ui)
    black = first('Noto Sans SC Black', 'Microsoft YaHei UI', 'MiSans', 'SimHei')
    mono = first('Cascadia Mono', 'JetBrains Mono', 'Consolas', 'Courier New')
    return ui, display, black, mono


def font(size=10, weight='normal', family=None):
    """生成 Tk 字体元组，方便业务代码复用主题字体。"""
    return (family or UI, size, weight)


def _hex(color):
    color = color.lstrip('#')
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(a, b, t):
    """两色线性插值，t=0 取 a，t=1 取 b。"""
    ca, cb = _hex(a), _hex(b)
    return _rgb(tuple(ca[i] + (cb[i] - ca[i]) * t for i in range(3)))


# ──────────────────────────────────────────────────────────────────────────
# 绘图小工具
# ──────────────────────────────────────────────────────────────────────────
def round_rect(canvas, x0, y0, x1, y1, r, **kw):
    """用平滑多边形在 Canvas 上画圆角矩形。"""
    pts = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


def vertical_gradient(canvas, width, height, stops, tag='gradient'):
    """竖向多段渐变；stops 为颜色列表（>=2）。"""
    canvas.delete(tag)
    if width <= 0 or height <= 0:
        return
    segments = len(stops) - 1
    for y in range(height):
        pos = (y / max(1, height - 1)) * segments
        i = min(int(pos), segments - 1)
        canvas.create_line(0, y, width, y, fill=mix(stops[i], stops[i + 1], pos - i), tags=tag)


def skew_band(canvas, x0, y0, x1, y1, band, gap, color, skew=20, **kw):
    """在矩形区域里铺一排平行四边形斜纹（Muse Dash 的警戒条）。"""
    kw.setdefault('outline', '')
    kw.setdefault('tags', 'stripe')
    step = band + gap
    x = x0 - abs(skew) - step
    while x < x1:
        canvas.create_polygon(x, y1, x + band, y1,
                              x + band + skew, y0, x + skew, y0,
                              fill=color, **kw)
        x += step


def halftone(canvas, x0, y0, x1, y1, step, radius, color, offset=0, **kw):
    """半调网点：交错排布的小圆点。"""
    kw.setdefault('outline', '')
    kw.setdefault('fill', color)
    kw.setdefault('tags', 'halftone')
    row = 0
    y = y0
    while y <= y1:
        x = x0 + (step / 2 if row % 2 else 0) + offset
        while x <= x1:
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, **kw)
            x += step
        y += step * 0.86
        row += 1


def outlined_text(canvas, x, y, text, font_tuple, fill, outline, width=3, anchor='w', **kw):
    """粗描边字：外圈铺一圈同色文字，再叠亮色字，模仿 Muse Dash 的标题描边。"""
    ids = []
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if (dx or dy) and dx * dx + dy * dy <= width * width + 1:
                ids.append(canvas.create_text(x + dx, y + dy, text=text, font=font_tuple,
                                              fill=outline, anchor=anchor, **kw))
    ids.append(canvas.create_text(x, y, text=text, font=font_tuple,
                                  fill=fill, anchor=anchor, **kw))
    return ids[-1]


def _star(canvas, cx, cy, r, color, inner=0.42, points=4, rot=-math.pi / 2, **kw):
    """四角星/六角星，用于粒子与高光。"""
    coords = []
    for i in range(points * 2):
        ang = rot + i * math.pi / points
        rad = r if i % 2 == 0 else r * inner
        coords.extend((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    kw.setdefault('outline', '')
    return canvas.create_polygon(coords, fill=color, **kw)


# ──────────────────────────────────────────────────────────────────────────
# 头图：斜条纹横幅 + 描边标题 + 小恶魔
# ──────────────────────────────────────────────────────────────────────────
class AnimeHeader(tk.Canvas):
    """顶部横幅：糖果渐变、斜条纹、半调网点、描边标题、锯齿边、流动的星光粒子。"""

    SPARK_SHAPE = ((0.0, -1.0), (0.42, -0.34), (1.0, -0.1), (0.42, 0.34),
                   (0.0, 1.0), (-0.42, 0.34), (-1.0, -0.1), (-0.42, -0.34))

    def __init__(self, master, title='Audio2Phira',
                 subtitle='本地制谱工作台   /   歌曲 → 谱面 → Phira',
                 badge='MUSE POP · LOCAL CHART LAB', height=150, **kw):
        kw.setdefault('bg', C.HEAD_1)
        super().__init__(master, height=height, highlightthickness=0, bd=0,
                         takefocus=0, **kw)
        self._title = title
        self._subtitle = subtitle
        self._badge = badge
        self._cw = 1
        self._ch = height
        self._phase = 0
        self._blink = False
        self._blink_cd = 0
        self._petals = []      # 兼容旧命名，实际存的是星光粒子
        self.bind('<Configure>', self._on_resize)
        self.after(60, self._animate)

    # ── 尺寸变化：重建整张头图
    def _on_resize(self, event=None):
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        if (width, height) == (self._cw, self._ch) and self.find_withtag('gradient'):
            return
        self._cw, self._ch = width, height
        self._render()
        self._spawn_petals()

    def _render(self):
        w, h = self._cw, self._ch
        self.delete('all')
        vertical_gradient(self, w, h, (C.HEAD_1, C.HEAD_2, C.HEAD_3, C.HEAD_4))

        # 右侧斜条纹 + 半调网点（只铺右半，避免压住标题）
        skew_band(self, w * 0.60, 0, w, h, 16, 30, mix(C.HEAD_3, C.YELLOW, 0.30), skew=26)
        halftone(self, w * 0.46, 8, w - 8, h - 26, 17, 1.9,
                 mix(C.PINK, C.HEAD_2, 0.45))

        # 左上大圆环（描边仪表盘感）
        self.create_oval(-70, -110, 190, 150, outline=mix(C.CYAN, C.HEAD_2, 0.35), width=2)
        self.create_oval(-40, -80, 160, 120, outline=mix(C.YELLOW, C.HEAD_3, 0.45), width=1)

        # 左上速度线
        for k in range(7):
            y = 22 + k * 15
            self.create_line(6, y, 6 + 34 + k * 9, y - 8, fill=mix(C.CYAN, C.HEAD_2, 0.45),
                             width=1)
            self.create_line(6, y + 29, 6 + 20 + k * 6, y + 22, fill=mix(C.YELLOW, C.HEAD_2, 0.5),
                             width=1)

        # 左侧竖色条
        self.create_rectangle(0, 0, 6, h, fill=C.PINK, outline='')
        self.create_rectangle(6, 0, 8, h, fill=C.INK, outline='')

        # 底部锯齿 + 霓虹线
        tooth = 16
        pts = []
        x = 0
        while x < w + tooth:
            pts.extend((x, h - 12, x + tooth / 2, h - 2, x + tooth, h - 12))
            x += tooth
        pts.extend((w, h, 0, h))
        self.create_polygon(pts, fill=C.INK, outline='')
        self.create_line(0, h - 13, w, h - 13, fill=C.YELLOW, width=2)
        self.create_line(0, h - 24, w, h - 24, fill=mix(C.PINK, C.INK, 0.45), width=4)

        # 徽标：平行四边形，亮黄底黑字黑边
        pad = 32
        badge_y = h * 0.205
        badge_font = font(8, 'bold', MONO)
        tmp = self.create_text(0, -100, text=self._badge, font=badge_font)
        bx0, by0, bx1, by1 = self.bbox(tmp)
        self.delete(tmp)
        bw, bh = bx1 - bx0, by1 - by0
        x0, y0 = pad, badge_y - bh / 2 - 4
        x1, y1 = pad + bw + 22, badge_y + bh / 2 + 4
        self.create_polygon(x0 + 9, y0, x1 + 9, y0, x1, y1, x0, y1,
                            fill=C.INK, outline='')
        self.create_polygon(x0 + 6, y0 - 3, x1 + 6, y0 - 3, x1 - 3, y1 - 3, x0 - 3, y1 - 3,
                            fill=C.YELLOW, outline=C.INK, width=2)
        self.create_text((x0 + x1) / 2 + 3, badge_y - 3, text=self._badge,
                         font=badge_font, fill=C.INK)

        # 主标题：粗描边
        title_y = h * 0.505
        outlined_text(self, pad + 2, title_y, self._title, (DISPLAY, 30),
                      '#ffffff', C.INK, width=2)

        # 副标题：黑底亮黄字条
        sub_font = font(10, 'bold')
        tmp = self.create_text(0, -100, text=self._subtitle, font=sub_font)
        sx0, sy0, sx1, sy1 = self.bbox(tmp)
        self.delete(tmp)
        sw, sh = sx1 - sx0, sy1 - sy0
        bx0, by0 = pad + 2, title_y + 28
        bx1, by1 = pad + sw + 22, title_y + 20 + sh + 10
        self.create_polygon(bx0 + 7, by0, bx1 + 7, by0, bx1, by1, bx0, by1,
                            fill=C.INK, outline='')
        self.create_polygon(bx0 + 5, by0 - 2, bx1 + 5, by0 - 2, bx1 - 2, by1 - 2, bx0 - 2, by1 - 2,
                            fill=mix(C.PINK, C.HEAD_2, 0.25), outline=C.YELLOW, width=1)
        self.create_text(bx0 + 12, by0 + sh / 2 + 4, text=self._subtitle,
                         font=sub_font, fill='#ffffff', anchor='w')

        # 角色
        if w > 560:
            self._draw_chibi(*self._chibi_geometry(), blink=self._blink)

    def _chibi_geometry(self):
        return (self._cw - 96, self._ch * 0.44,
                min(0.94, (self._ch - 26) / 150.0))

    # ── 星光粒子
    def _petal_points(self, petal):
        r, ang = petal['r'], petal['a']
        ca, sa = math.cos(ang), math.sin(ang)
        pts = []
        for px, py in self.SPARK_SHAPE:
            pts.extend((petal['x'] + (px * ca - py * sa) * r,
                        petal['y'] + (px * sa + py * ca) * r))
        return pts

    def _spawn_petals(self):
        for petal in self._petals:
            try:
                self.delete(petal['id'])
            except tk.TclError:
                pass
        self._petals = []
        rnd = random.Random(99)
        colors = (C.YELLOW, C.CYAN, C.PINK_HI, C.PINK_SOFT, C.LIME)
        for _ in range(18):
            r = rnd.uniform(2.4, 5.6)
            petal = {
                'x': rnd.uniform(0, self._cw),
                'y': rnd.uniform(0, self._ch),
                'r': r,
                'a': rnd.uniform(0, math.tau),
                'spin': rnd.choice((-1, 1)) * rnd.uniform(0.02, 0.07),
                'vy': -rnd.uniform(0.25, 0.95),
                'vx': rnd.uniform(-0.35, 0.35),
                'sw': rnd.uniform(24, 60),
                'sa': rnd.uniform(0.4, 1.3),
                'ph': rnd.uniform(0, math.tau),
                'color': rnd.choice(colors),
            }
            petal['id'] = self.create_polygon(self._petal_points(petal),
                                              fill=petal['color'], outline='',
                                              tags='spark')
            self._petals.append(petal)

    def _animate(self):
        self._phase += 1
        try:
            if not self.winfo_exists():
                return
            h = self._ch
            for petal in self._petals:
                petal['y'] += petal['vy']
                petal['x'] += petal['vx'] + math.sin((self._phase + petal['ph']) / petal['sw']) * petal['sa']
                petal['a'] += petal['spin']
                if petal['y'] < -14:
                    petal['y'] = h + 12
                    petal['x'] = random.uniform(0, max(1, self._cw))
                elif petal['x'] < -16:
                    petal['x'] = self._cw + 14
                elif petal['x'] > self._cw + 16:
                    petal['x'] = -14
                self.coords(petal['id'], *self._petal_points(petal))

            if self._blink_cd > 0:
                self._blink_cd -= 1
                if self._blink_cd == 0:
                    self._blink = False
                    self._redraw_face()
            elif self._phase % 54 == 0:
                self._blink = True
                self._blink_cd = 4
                self._redraw_face()
            self.after(60, self._animate)
        except tk.TclError:
            return

    def _redraw_face(self):
        if self._cw <= 560:
            return
        cx, cy, size = self._chibi_geometry()
        self.delete('face')
        self._draw_face(cx, cy, size, self._blink)

    # ── 小恶魔系角色（参考 Muse Dash 的吸血鬼妹妹气质）
    def _draw_chibi(self, cx, cy, s, blink):
        self.delete('chibi')
        self.delete('face')
        hair = '#2b0f45'
        hair_hi = C.PURPLE
        hair_hi2 = C.PINK
        skin = '#ffe7f2'
        skin_shade = '#ffc4dd'
        ink = C.INK

        def P(x, y):
            return cx + x * s, cy + y * s

        def oval(x0, y0, x1, y1, **kw):
            a, b = P(x0, y0), P(x1, y1)
            kw.setdefault('tags', 'chibi')
            kw.setdefault('outline', '')
            return self.create_oval(a[0], a[1], b[0], b[1], **kw)

        def poly(points, **kw):
            coords = []
            for x, y in points:
                px, py = P(x, y)
                coords.extend((px, py))
            kw.setdefault('tags', 'chibi')
            kw.setdefault('outline', '')
            return self.create_polygon(coords, **kw)

        def line(points, **kw):
            coords = []
            for x, y in points:
                px, py = P(x, y)
                coords.extend((px, py))
            kw.setdefault('tags', 'chibi')
            return self.create_line(coords, **kw)

        # 背景圆盘（唱片感）
        ox, oy = P(0, 4)
        self.create_oval(ox - 62 * s, oy - 62 * s, ox + 62 * s, oy + 62 * s,
                         fill='', outline=mix(C.YELLOW, C.HEAD_2, 0.25),
                         width=max(1, int(2 * s)), tags='chibi')
        self.create_oval(ox - 54 * s, oy - 54 * s, ox + 54 * s, oy + 54 * s,
                         fill='', outline=mix(C.CYAN, C.HEAD_2, 0.4),
                         width=max(1, int(1 * s)), tags='chibi')

        # 双马尾
        poly([(-30, -22), (-66, -46), (-74, 6), (-46, 22), (-34, 2)], fill=hair)
        poly([(30, -22), (66, -46), (74, 6), (46, 22), (34, 2)], fill=hair)
        poly([(-36, -18), (-62, -38), (-66, -6)], fill=hair_hi2)
        poly([(36, -18), (62, -38), (66, -6)], fill=hair_hi2)
        poly([(-58, 4), (-52, 26), (-42, 10)], fill=hair_hi)
        poly([(58, 4), (52, 26), (42, 10)], fill=hair_hi)

        # 恶魔角
        poly([(-26, -48), (-34, -76), (-12, -58)], fill=C.PINK, outline=ink)
        poly([(26, -48), (34, -76), (12, -58)], fill=C.PINK, outline=ink)

        # 肩膀 / 衣领
        oval(-46, 26, 46, 80, fill='#f4ecff')
        poly([(-28, 30), (0, 48), (28, 30), (20, 26), (0, 38), (-20, 26)], fill=C.CYAN)
        poly([(0, 44), (11, 55), (0, 70), (-11, 55)], fill=C.PINK, outline=ink)

        # 头
        oval(-34, -56, 34, 26, fill=hair)
        oval(-28, -40, 28, 24, fill=skin)
        oval(-20, 8, 20, 24, fill=skin_shade)

        # 刘海（锯齿状，Muse 味）
        poly([(-31, -26), (-26, -48), (-8, -52), (8, -51), (24, -44), (31, -26),
              (20, -32), (12, -20), (2, -30), (-8, -19), (-18, -30), (-25, -22)], fill=hair)
        poly([(-26, -42), (-8, -50), (10, -46), (2, -34), (-12, -38)], fill=hair_hi)
        poly([(-4, -48), (6, -50), (2, -40)], fill=hair_hi2)

        # 呆毛
        line([(2, -54), (10, -74), (-8, -78)], fill=hair, width=max(2, int(6 * s)),
             smooth=True)

        # 眼睛
        self._draw_face(cx, cy, s, blink)

        # 腮红 + 条纹
        oval(-25, 4, -12, 14, fill='#ff8fc4')
        oval(12, 4, 25, 14, fill='#ff8fc4')
        for k in range(3):
            line([(-24 + k * 3, 5), (-20 + k * 3, 13)], fill='#ff5f9e',
                 width=max(1, int(1.4 * s)))
            line([(13 + k * 3, 5), (17 + k * 3, 13)], fill='#ff5f9e',
                 width=max(1, int(1.4 * s)))

        # 锯齿嘴
        line([(-8, 15), (-4, 21), (0, 15), (4, 21), (8, 15)], fill=ink,
             width=max(1, int(2 * s)), smooth=False)

    def _draw_face(self, cx, cy, s, blink):
        """斜挑眼 + 十字星高光；眨眼只重画这一层。"""
        def P(x, y):
            return cx + x * s, cy + y * s

        eye = '#2a0a3d'
        for ex, ey in ((-20, -6), (7, -6)):
            x0, y0 = P(ex, ey - 12)
            x1, y1 = P(ex + 13, ey + 9)
            if blink:
                mx, my = P(ex, ey)
                self.create_line(x0 + 1, my, x1 - 1, my, fill=eye,
                                 width=max(2, int(3.2 * s)), tags='face', capstyle='round')
                continue
            self.create_polygon(x0, y0, x1, y0 + 2 * s, x1 - 1 * s, y1, x0 + 1 * s, y1 - 2 * s,
                                fill=eye, outline='', tags='face')
            ix0, iy0 = P(ex + 2, ey - 3)
            ix1, iy1 = P(ex + 11, ey + 7)
            self.create_oval(ix0, iy0, ix1, iy1, fill=C.PINK, outline='', tags='face')
            jx0, jy0 = P(ex + 3, ey + 1)
            jx1, jy1 = P(ex + 9, ey + 7)
            self.create_oval(jx0, jy0, jx1, jy1, fill=C.YELLOW, outline='', tags='face')
            # 十字星高光
            _star(self, *P(ex + 5.5, ey - 6), 3.4 * s, '#ffffff', tags='face')
            hx, hy = P(ex + 10.5, ey + 4)
            hs = 1.5 * s
            self.create_oval(hx - hs, hy - hs, hx + hs, hy + hs,
                             fill='#ffffff', outline='', tags='face')
            # 上睫毛（粗，斜挑）
            lx0, ly0 = P(ex - 2, ey - 11)
            lx1, ly1 = P(ex + 14, ey - 13)
            self.create_line(lx0, ly0, lx1, ly1, fill=eye,
                             width=max(2, int(3 * s)), tags='face', capstyle='round')


# ──────────────────────────────────────────────────────────────────────────
# ttk 样式：全部粗描边 + 高饱和
# ──────────────────────────────────────────────────────────────────────────
def _base(style):
    style.configure('.', font=(UI, 10), background=C.BG, foreground=C.TEXT,
                    fieldbackground=C.INPUT, bordercolor=C.INK,
                    focuscolor=C.PINK, lightcolor=C.CARD, darkcolor=C.CARD,
                    troughcolor=C.BG_ALT, selectbackground=C.PINK,
                    selectforeground=C.INK, insertcolor=C.YELLOW)
    style.configure('TFrame', background=C.BG, borderwidth=0)
    style.configure('Card.TFrame', background=C.CARD)
    style.configure('Header.TFrame', background=C.HEAD_1)


def _labels(style):
    style.configure('TLabel', background=C.BG, foreground=C.TEXT)
    style.configure('Card.TLabel', background=C.CARD, foreground=C.TEXT)
    style.configure('Muted.TLabel', background=C.BG, foreground=C.TEXT_DIM)
    style.configure('Hint.TLabel', background=C.BG, foreground=C.TEXT_FAINT,
                    font=(UI, 9))
    style.configure('Pill.TLabel', background=C.CARD, foreground=C.YELLOW,
                    padding=(16, 8), font=(BLACK, 10), borderwidth=2,
                    relief='solid', bordercolor=C.YELLOW)
    style.configure('Title.TLabel', background=C.BG, foreground=C.TEXT,
                    font=(BLACK, 15))
    style.configure('TSeparator', background=C.PINK)


def _entries(style):
    _safe(style, 'TEntry', fieldbackground=C.INPUT, foreground=C.TEXT,
          bordercolor=C.CYAN, lightcolor=C.INPUT, darkcolor=C.INPUT,
          insertcolor=C.YELLOW, padding=(10, 8), borderwidth=2, relief='solid')
    _safe(style, 'TCombobox', fieldbackground=C.INPUT, foreground=C.TEXT,
          background=C.CARD, bordercolor=C.CYAN, arrowcolor=C.YELLOW,
          lightcolor=C.INPUT, darkcolor=C.INPUT, padding=(10, 7),
          borderwidth=2,
          selectbackground=C.INPUT, selectforeground=C.TEXT)
    style.map('TCombobox',
              fieldbackground=[('readonly', C.INPUT), ('disabled', C.BG_ALT)],
              foreground=[('disabled', C.TEXT_FAINT)],
              background=[('active', C.PURPLE), ('readonly', C.PURPLE)],
              arrowcolor=[('active', C.INK), ('disabled', C.TEXT_FAINT)],
              bordercolor=[('active', C.YELLOW)],
              selectbackground=[('readonly', C.INPUT)],
              selectforeground=[('readonly', C.TEXT)])
    _safe(style, 'TCheckbutton', background=C.BG, foreground=C.TEXT,
          indicatorbackground=C.INPUT, indicatorforeground=C.INK,
          bordercolor=C.INK, focuscolor=C.BG, padding=(2, 4))
    style.map('TCheckbutton',
              background=[('active', C.BG)],
              foreground=[('active', C.YELLOW), ('disabled', C.TEXT_FAINT)],
              indicatorbackground=[('selected', C.YELLOW), ('active', C.PURPLE)],
              indicatorforeground=[('selected', C.INK)])
    _safe(style, 'TRadiobutton', background=C.BG, foreground=C.TEXT,
          indicatorbackground=C.INPUT, indicatorforeground=C.INK,
          bordercolor=C.INK, focuscolor=C.BG)
    style.map('TRadiobutton',
              background=[('active', C.BG)],
              foreground=[('active', C.YELLOW)],
              indicatorbackground=[('selected', C.YELLOW)])


def _buttons(style):
    # 普通按钮：毒紫块 + 3px 黑边，像贴纸
    style.configure('TButton', background=C.PURPLE, foreground='#ffffff',
                    bordercolor=C.INK, lightcolor=C.PURPLE, darkcolor=C.PURPLE,
                    borderwidth=3, relief='solid', focusthickness=0,
                    focuscolor=C.PINK, padding=(16, 8), font=(BLACK, 10))
    style.map('TButton',
              background=[('disabled', C.BG_ALT), ('pressed', C.PINK),
                          ('active', mix(C.PURPLE, C.PINK, 0.35))],
              foreground=[('disabled', C.TEXT_FAINT), ('active', '#ffffff')],
              bordercolor=[('active', C.YELLOW)])
    # 强调按钮：品红块 + 3px 黑边 + 黑字，Muse Dash 的主行动按钮
    style.configure('Accent.TButton', background=C.PINK, foreground=C.INK,
                    bordercolor=C.INK, lightcolor=C.PINK, darkcolor=C.PINK,
                    borderwidth=4, relief='solid', padding=(26, 10),
                    font=(BLACK, 12))
    style.map('Accent.TButton',
              background=[('disabled', '#4a2044'), ('pressed', C.YELLOW),
                          ('active', C.PINK_HI)],
              foreground=[('disabled', C.TEXT_FAINT), ('active', C.INK)],
              bordercolor=[('active', C.YELLOW)])
    style.configure('Ghost.TButton', background=C.BG_ALT, foreground=C.CYAN,
                    bordercolor=C.CYAN, borderwidth=2, padding=(14, 7))


def _notebook(style):
    style.configure('TNotebook', background=C.BG, borderwidth=0,
                    tabmargins=(4, 8, 4, 0))
    style.configure('TNotebook.Tab', background=C.CARD, foreground=C.TEXT_DIM,
                    borderwidth=3, relief='solid', bordercolor=C.INK,
                    lightcolor=C.CARD, darkcolor=C.CARD,
                    padding=(22, 9), font=(BLACK, 10))
    style.map('TNotebook.Tab',
              background=[('selected', C.PINK), ('active', C.PURPLE)],
              foreground=[('selected', C.INK), ('active', '#ffffff')],
              bordercolor=[('selected', C.YELLOW)],
              lightcolor=[('selected', C.PINK)],
              expand=[('selected', (0, 0, 0, 3))])
    _safe(style, 'TNotebook.Client', background=C.BG, borderwidth=0)


def _frames(style):
    _safe(style, 'TLabelframe', background=C.BG, bordercolor=C.INK,
          borderwidth=3, relief='solid', lightcolor=C.BG, darkcolor=C.BG,
          padding=(18, 12))
    style.configure('TLabelframe.Label', background=C.PINK, foreground=C.INK,
                    font=(BLACK, 10), padding=(8, 2))


def _trees(style):
    style.configure('Treeview', background=C.INPUT, fieldbackground=C.INPUT,
                    foreground=C.TEXT, bordercolor=C.INK,
                    lightcolor=C.INPUT, darkcolor=C.INPUT,
                    borderwidth=2, relief='solid', rowheight=32,
                    font=(UI, 10))
    style.map('Treeview',
              background=[('selected', C.PINK)],
              foreground=[('selected', C.INK)])
    style.configure('Treeview.Heading', background=C.CYAN, foreground=C.INK,
                    borderwidth=2, relief='solid', bordercolor=C.INK,
                    padding=(10, 8), font=(BLACK, 10))
    style.map('Treeview.Heading',
              background=[('active', C.YELLOW)],
              foreground=[('active', C.INK)])


def _bars(style):
    style.configure('Horizontal.TProgressbar', background=C.PINK,
                    troughcolor=C.INK, bordercolor=C.INK,
                    lightcolor=C.PINK, darkcolor=C.PINK, thickness=12,
                    borderwidth=2, relief='solid')
    style.configure('Vertical.TProgressbar', background=C.PINK,
                    troughcolor=C.INK, bordercolor=C.INK,
                    lightcolor=C.PINK, darkcolor=C.PINK, thickness=12)
    style.configure('TScrollbar', background=C.CYAN, troughcolor=C.INK,
                    bordercolor=C.INK, arrowcolor=C.YELLOW, gripcount=0,
                    lightcolor=C.CYAN, darkcolor=C.CYAN, width=13,
                    borderwidth=2, relief='solid')
    style.map('TScrollbar',
              background=[('active', C.YELLOW), ('pressed', C.PINK)],
              arrowcolor=[('active', C.INK)])
    for orient in ('Vertical', 'Horizontal'):
        try:
            style.layout('%s.TScrollbar' % orient, [
                ('%s.Scrollbar.trough' % orient, {
                    'children': [('%s.Scrollbar.thumb' % orient,
                                  {'expand': '1', 'sticky': 'nswe'})],
                    'sticky': 'ns' if orient == 'Vertical' else 'ew',
                }),
            ])
        except tk.TclError:
            pass


def _misc(style):
    _safe(style, 'TSizegrip', background=C.BG_ALT)


def _safe(style, name, **options):
    """逐项配置，遇到当前 Tk/主题不支持的选项就跳过，绝不让界面起不来。"""
    for key, value in options.items():
        try:
            style.configure(name, **{key: value})
        except tk.TclError:
            pass


def dark_titlebar(root):
    """把 Windows 原生标题栏也刷成深紫（Win10/11，失败则静默跳过）。"""
    try:
        import ctypes

        root.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        flag = ctypes.c_int(1)
        for attr in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(flag), ctypes.sizeof(flag))
            except Exception:
                pass
        for attr, value in ((35, 0x00280A17),      # DWMWA_CAPTION_COLOR = #170a28 (BGR)
                            (36, 0x00FFE14D)):     # DWMWA_TEXT_COLOR
            try:
                color = ctypes.c_int(value)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(color), ctypes.sizeof(color))
            except Exception:
                pass
    except Exception:
        pass


def apply(root):
    """把 Muse 波普画风装到 root 上，返回 ttk.Style 实例。"""
    global UI, DISPLAY, BLACK, MONO, CJK
    UI, DISPLAY, BLACK, MONO = pick_fonts(root)
    CJK = UI

    root.configure(bg=C.BG)
    root.option_add('*Font', (UI, 10))
    root.option_add('*Background', C.BG)
    root.option_add('*Foreground', C.TEXT)
    root.option_add('*TCombobox*Listbox.background', C.CARD)
    root.option_add('*TCombobox*Listbox.foreground', C.TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', C.PINK)
    root.option_add('*TCombobox*Listbox.selectForeground', C.INK)
    root.option_add('*TCombobox*Listbox.font', (UI, 10))
    root.option_add('*Menu.background', C.CARD)
    root.option_add('*Menu.foreground', C.TEXT)
    root.option_add('*Menu.activeBackground', C.PINK)
    root.option_add('*Menu.activeForeground', C.INK)

    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass

    _base(style)
    _labels(style)
    _entries(style)
    _buttons(style)
    _notebook(style)
    _frames(style)
    _trees(style)
    _bars(style)
    _misc(style)
    try:
        root.after(60, lambda: dark_titlebar(root))
    except Exception:
        pass
    return style
