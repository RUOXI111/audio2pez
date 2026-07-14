"""
audio2pez — 音频 → PhiraEdit 谱面生成器
主入口

用法:
  python main.py <音频文件> [选项]
  python main.py input.mp3
  python main.py input.mp3 --bpm 140 --level "IN 15"
  python main.py input.mp3 --name "My Song" --charter "Me"
"""

import os
import sys
import argparse

from analyze import (
    load_audio, detect_bpm, detect_beats,
    detect_onsets, spectral_analysis, detect_sections
)
from chart_generator import ChartGenerator
from config import DIFFICULTY_PRESETS
from pez_packager import build_chart_json, pack_pez, save_json


def main():
    parser = argparse.ArgumentParser(
        description="audio2pez — 音频转 PhiraEdit 谱面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py song.mp3
  python main.py song.wav --bpm 140 --level "IN 15"
  python main.py song.mp3 --name "My Song" --charter "Claude" --offset 50
        """
    )
    parser.add_argument("input", help="输入音频文件 (.mp3, .wav, .ogg, .flac...)")
    parser.add_argument("--bpm", type=float, default=None, help="手动指定 BPM (不指定则自动检测)")
    parser.add_argument("--name", type=str, default=None, help="谱面名称")
    parser.add_argument("--level", type=str, default="IN 13", help="难度标识 (默认: IN 13)")
    parser.add_argument("--charter", type=str, default="auto-generated", help="谱师名")
    parser.add_argument("--composer", type=str, default="Unknown", help="作曲者")
    parser.add_argument("--offset", type=int, default=0, help="音频偏移 (ms)")
    parser.add_argument("--outdir", type=str, default="output", help="输出目录")
    parser.add_argument("--difficulty", type=str, default="hard",
                        choices=["easy", "hard"], help="难度: easy (IN 8) / hard (IN 14)")
    parser.add_argument("--bpm-only", action="store_true", help="仅检测 BPM, 不生成谱面")
    args = parser.parse_args()

    audio_path = os.path.abspath(args.input)
    if not os.path.exists(audio_path):
        print(f"错误: 文件不存在: {audio_path}")
        sys.exit(1)

    song_name = args.name or os.path.splitext(os.path.basename(audio_path))[0]

    print("=" * 60)
    print(f"  audio2pez — 音频转谱面")
    print(f"  输入: {audio_path}")
    print(f"  曲名: {song_name}")
    print("=" * 60)

    # ── 第 1 步: 音频分析 ──────────────────────────
    print("\n[Step 1/4] 音频分析...")
    y, sr = load_audio(audio_path)

    if args.bpm:
        bpm = args.bpm
        print(f"[analyze] 手动 BPM: {bpm}")
    else:
        bpm = detect_bpm(y, sr)

    beat_times = detect_beats(y, sr, bpm)

    if args.bpm_only:
        print(f"\nBPM: {bpm:.1f}")
        print(f"节拍数: {len(beat_times)}")
        print(f"时长: {len(y)/sr:.1f}s")
        return

    _onset_times, onset_env = detect_onsets(y, sr)
    bands = spectral_analysis(y, sr)
    sections = detect_sections(y, sr, beat_times)

    # ── 第 2 步: 谱面生成 ──────────────────────────
    print("\n[Step 2/4] 谱面生成...")
    difficulty = DIFFICULTY_PRESETS[args.difficulty]
    gen = ChartGenerator(
        bpm=bpm,
        beat_times=beat_times,
        onset_env=onset_env,
        bands=bands,
        sections=sections,
        difficulty=difficulty,
        sr=sr,
    )
    notes = gen.generate()
    events = gen.generate_events()

    if not notes:
        print("错误: 没有生成任何音符! 请调整参数或尝试其他音频。")
        sys.exit(1)

    # ── 第 3 步: 构建 JSON ──────────────────────────
    print("\n[Step 3/4] 构建谱面 JSON...")
    meta = {
        "id": song_name,
        "name": song_name,
        "level": args.level if args.level != "IN 13" else difficulty["level_tag"],
        "charter": args.charter,
        "composer": args.composer,
        "offset": args.offset,
        "background": f"{song_name}.jpg",
        "song": f"{song_name}.mp3",
    }
    chart_json = build_chart_json(bpm, notes, events, meta)

    # ── 第 4 步: 打包输出 ──────────────────────────
    print("\n[Step 4/4] 打包 .pez ...")

    # 检查是否有同名的 jpg 图片
    image_path = None
    for ext in ('.jpg', '.jpeg', '.png'):
        candidate = os.path.splitext(audio_path)[0] + ext
        if os.path.exists(candidate):
            image_path = candidate
            break

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.outdir)
    pez_path = pack_pez(audio_path, output_dir, chart_json, image_path)
    save_json(chart_json, output_dir)

    # ── 统计 ───────────────────────────────────────
    types = {}
    for n in notes:
        t = n["type"]
        types[t] = types.get(t, 0) + 1
    type_names = {1: "Tap", 2: "Hold", 3: "Flick", 4: "Drag"}

    print("\n" + "=" * 60)
    print("  生成完毕!")
    print(f"  BPM: {bpm}")
    print(f"  音符总数: {len(notes)}")
    for t, count in sorted(types.items()):
        print(f"    {type_names.get(t, t)}: {count}")
    print(f"  输出: {pez_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
