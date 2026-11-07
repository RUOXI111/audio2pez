# -*- coding: utf-8 -*-
"""生成 Audio2Phira 的小恶魔像素头像图标（多尺寸 .ico）。

用法：
    python make_icon.py            # 写到项目 .desktop/app.ico
输出：
    <Project>/.desktop/app.ico     多尺寸图标（16/24/32/48/64/128/256）
    icon_preview.png               各尺寸预览图，便于肉眼核对
"""

from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# ── 调色板（与 anime_theme.C 对齐）
INK = (13, 5, 24, 255)
DISC = (36, 16, 64, 255)
HAIR = (43, 15, 69, 255)
HAIR_HI = (155, 92, 255, 255)
PINK = (255, 61, 154, 255)
PINK_SOFT = (255, 201, 230, 255)
SKIN = (255, 231, 242, 255)
BLUSH = (255, 143, 196, 255)
EYE = (42, 10, 61, 255)
YELLOW = (255, 225, 77, 255)
CYAN = (34, 224, 230, 255)
WHITE = (255, 255, 255, 255)

BASIS = 256.0


def _draw_avatar(draw: ImageDraw.ImageDraw, size: int) -> None:
    """在 size×size 画布上按 256 基准坐标绘制头像。"""
    k = size / BASIS

    def s(*v):
        return tuple(round(x * k) for x in v)

    def box(x0, y0, x1, y1):
        return [round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k)]

    def w(v):
        return max(1, round(v * k))

    # 圆底唱片
    draw.ellipse(box(5, 5, 251, 251), fill=DISC, outline=INK, width=w(8))
    draw.ellipse(box(20, 20, 236, 236), outline=(70, 34, 116, 255), width=w(2))

    # 双马尾（贴边，32px 下作为暗部边缘）
    draw.polygon([s(52, 104), s(22, 146), s(18, 220), s(52, 210), s(62, 150)], fill=HAIR)
    draw.polygon([s(204, 104), s(234, 146), s(238, 220), s(204, 210), s(194, 150)], fill=HAIR)
    draw.polygon([s(30, 158), s(22, 200), s(42, 192)], fill=PINK)
    draw.polygon([s(226, 158), s(234, 200), s(214, 192)], fill=PINK)

    # 恶魔角（大而尖，32px 下依然清楚）
    draw.polygon([s(74, 86), s(44, 2), s(124, 52)], fill=PINK, outline=INK, width=w(7))
    draw.polygon([s(182, 86), s(212, 2), s(132, 52)], fill=PINK, outline=INK, width=w(7))

    # 头 + 脸（脸占中央大半，保证小尺寸可读）
    draw.ellipse(box(54, 40, 202, 236), fill=HAIR, outline=INK, width=w(5))
    draw.ellipse(box(70, 84, 186, 222), fill=SKIN)

    # 刘海（三齿，齿深大，小尺寸下脸的上边界才干净）
    draw.polygon([s(58, 112), s(64, 64), s(96, 46), s(128, 42), s(160, 46), s(192, 64),
                  s(198, 112), s(170, 84), s(128, 116), s(86, 84)],
                 fill=HAIR)
    # 挑染
    draw.polygon([s(66, 92), s(72, 62), s(102, 54), s(94, 82)], fill=HAIR_HI)
    draw.polygon([s(152, 52), s(184, 60), s(190, 86), s(160, 70)], fill=HAIR_HI)
    draw.polygon([s(120, 48), s(140, 44), s(134, 68), s(118, 72)], fill=PINK)

    # 呆毛
    draw.line([s(132, 44), s(146, 16), s(116, 8)], fill=HAIR, width=w(7), joint='curve')

    # 眼睛
    for ex in (96, 132):
        draw.ellipse(box(ex, 128, ex + 28, 164), fill=EYE)
        draw.ellipse(box(ex + 4, 133, ex + 24, 161), fill=PINK)
        draw.ellipse(box(ex + 7, 139, ex + 21, 159), fill=YELLOW)
        cx, cy, r = ex + 13, 138, 6
        draw.polygon([s(cx, cy - r), s(cx + r * 0.34, cy - r * 0.3),
                      s(cx + r, cy), s(cx + r * 0.34, cy + r * 0.3),
                      s(cx, cy + r), s(cx - r * 0.34, cy + r * 0.3),
                      s(cx - r, cy), s(cx - r * 0.34, cy - r * 0.3)],
                     fill=WHITE)
        # 上睫毛
        draw.line([s(ex - 5, 126), s(ex + 33, 120)], fill=EYE, width=w(6))

    # 腮红 + 条纹
    for bx in (76, 156):
        draw.ellipse(box(bx, 182, bx + 24, 198), fill=BLUSH)
    for i in range(3):
        draw.line([s(80 + i * 7, 184), s(84 + i * 7, 196)], fill=(255, 95, 158, 255), width=w(2))
        draw.line([s(160 + i * 7, 184), s(164 + i * 7, 196)], fill=(255, 95, 158, 255), width=w(2))

    # 嘴：短弧线，小尺寸下不断裂
    draw.line([s(112, 200), s(128, 212), s(144, 200)],
              fill=INK, width=w(7), joint='curve')

    # 领口：一小截青色弧 + 粉领结，别抢脸的面积
    draw.ellipse(box(88, 222, 168, 286), fill=(244, 236, 255, 255))
    draw.polygon([s(104, 228), s(128, 246), s(152, 228), s(143, 224), s(128, 238), s(113, 224)],
                 fill=CYAN)
    draw.polygon([s(128, 242), s(139, 253), s(128, 266), s(117, 253)], fill=PINK, outline=INK,
                 width=w(3))


def render(size: int, supersample: int = 4) -> Image.Image:
    """渲染指定尺寸的图标；超采样后缩小得到平滑边缘。"""
    work = size * supersample
    img = Image.new('RGBA', (work, work), (0, 0, 0, 0))
    _draw_avatar(ImageDraw.Draw(img), work)
    if supersample > 1:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def _bmp_entry(im: Image.Image) -> bytes:
    """把 RGBA 图编码成 ICO 里的 BMP(DIB) 条目。

    .NET Framework 的 System.Drawing.Icon 不认 PNG 压缩条目，
    小尺寸用 BMP 才能被 WinForms / 资源管理器稳定读取。
    """
    w, h = im.size
    px = im.load()
    xor_rows = []
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))
        xor_rows.append(bytes(row))
    xor = b''.join(xor_rows)

    mask_stride = ((w + 31) // 32) * 4
    mask_rows = []
    for y in range(h - 1, -1, -1):
        bits = bytearray(mask_stride)
        for x in range(w):
            if px[x, y][3] == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask_rows.append(bytes(bits))
    mask = b''.join(mask_rows)

    header = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0,
                         len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + mask


def write_ico(path: Path, images) -> None:
    """手写 ICO：<=64 用 BMP 条目（.NET/WinForms 兼容），128/256 用 PNG 条目。"""
    entries = b''
    blobs = []
    offset = 6 + 16 * len(images)
    for im in images:
        if im.size[0] <= 64:
            data = _bmp_entry(im)
        else:
            buf = io.BytesIO()
            im.save(buf, format='PNG')
            data = buf.getvalue()
        width = 0 if im.size[0] >= 256 else im.size[0]
        height = 0 if im.size[1] >= 256 else im.size[1]
        entries += struct.pack('<BBBBHHII', width, height, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs.append(data)
    with path.open('wb') as stream:
        stream.write(struct.pack('<HHH', 0, 1, len(images)))
        stream.write(entries)
        for blob in blobs:
            stream.write(blob)


def main() -> int:
    base = Path(__file__).resolve().parent
    if len(sys.argv) > 1:
        base = Path(sys.argv[1]).resolve()
    state = base / '.desktop'
    state.mkdir(parents=True, exist_ok=True)

    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = [render(size) for size in sizes]
    write_ico(state / 'app.ico', images)

    # 预览：各尺寸横向排列在棋盘格上
    pad = 12
    total = sum(s + pad for s in sizes) + pad
    preview = Image.new('RGBA', (total, 256 + pad * 2), (26, 12, 46, 255))
    x = pad
    for size, im in zip(sizes, images):
        y = pad + (256 - size) // 2
        preview.alpha_composite(im, (x, y))
        x += size + pad
    preview.save(base / 'icon_preview.png')

    ico = state / 'app.ico'
    print('icon written: %s (%d bytes, %d sizes)' % (ico, ico.stat().st_size, len(sizes)))
    print('preview: %s' % (base / 'icon_preview.png'))

    # 安装器横幅用的位图（.NET Icon 类读 PNG 条目不可靠，这里直接给 PNG）
    render(256, supersample=4).save(state / 'app.png')
    print('bitmap: %s' % (state / 'app.png'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
