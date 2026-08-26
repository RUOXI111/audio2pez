# -*- coding: utf-8 -*-
"""audio2pez 命令行入口：把任意音频转成可导入 Phira 的 .pez。

用法:
  python main.py song.mp3
  python main.py song.mp3 --difficulty hard --line-fx mix
  python main.py song.mp3 --all-tiers --key 4k
"""

import argparse
import os
import sys

from generate import generate
from config import DIFFICULTY_PRESETS

LINE_FX = ["none", "alpha_pulse", "pinwheel", "grid", "curve", "color_flow",
           "glow", "bounce", "breathe", "meteor", "echo_trail", "spotlight", "mix"]
KEYS = ["auto", "2k", "4k", "6k"]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="audio2pez - 音频转 PhiraEdit 谱面生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="输入音频文件 (.mp3/.wav/.ogg/.flac)")
    parser.add_argument("--bpm", type=float, default=None, help="手动指定 BPM（不指定则自动检测）")
    parser.add_argument("--difficulty", default="hard", choices=list(DIFFICULTY_PRESETS),
                        help="难度分级")
    parser.add_argument("--all-tiers", action="store_true", help="一次输出全部 5 档难度")
    parser.add_argument("--name", default=None, help="谱面名称/曲名")
    parser.add_argument("--artist", default="", help="曲师 / Artist")
    parser.add_argument("--charter", default=None, help="谱师 / Charter")
    parser.add_argument("--cover", default=None, help="封面图片路径（可选）")
    parser.add_argument("--outdir", default="output", help="输出目录")
    parser.add_argument("--key", default="auto", choices=KEYS, help="判定线轨道数")
    parser.add_argument("--line-fx", default="none", choices=LINE_FX, help="判定线动效")
    parser.add_argument("--pulse-style", default="chain", choices=["chain", "sweep"],
                        help="pulse 侧闪形态")
    parser.add_argument("--deco-when", default="intro_chorus",
                        choices=["intro_chorus", "intro", "chorus", "verse", "repeat", "all"],
                        help="旋转装饰出现段落")
    parser.add_argument("--main-y", type=float, default=-300.0, help="主判定线初始 Y")
    parser.add_argument("--mix-spec", default="", help="mix 特效顺序 effect@段落;…")
    parser.add_argument("--main-swing", action="store_true", help="主判定线左右摆动")
    parser.add_argument("--density", type=float, default=1.0, help="写谱密度/难度倍率")
    parser.add_argument("--tap-weight", type=float, default=None)
    parser.add_argument("--hold-weight", type=float, default=None)
    parser.add_argument("--flick-weight", type=float, default=None)
    parser.add_argument("--drag-weight", type=float, default=None)
    args = parser.parse_args(argv)

    audio = os.path.abspath(args.input)
    if not os.path.exists(audio):
        print(f"错误: 文件不存在 {audio}", file=sys.stderr)
        return 1

    out = generate(
        audio_path=audio,
        difficulty=args.difficulty,
        bpm=args.bpm,
        all_tiers=args.all_tiers,
        image_path=args.cover,
        title=(args.name or "").strip() or None,
        artist=(args.artist or "").strip(),
        charter_name=(args.charter or "").strip() or None,
        outdir=args.outdir,
        density_mult=args.density,
        line_fx=args.line_fx,
        pulse_style=args.pulse_style,
        deco_when=args.deco_when,
        main_y=args.main_y,
        mix_spec=(args.mix_spec or "").strip(),
        key_mode=args.key,
        main_swing=bool(args.main_swing),
        tap_weight=args.tap_weight,
        hold_weight=args.hold_weight,
        flick_weight=args.flick_weight,
        drag_weight=args.drag_weight,
    )
    print("=" * 64)
    for tier, path in out["results"].items():
        print(f"  [{tier}] {path}")
    print("=" * 64)
    print(out["log"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
