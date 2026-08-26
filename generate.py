# -*- coding: utf-8 -*-
"""audio2pez 流水线：音频检测 -> 频谱/段落分析 -> 难度分级排布 -> 打包 .pez。"""

import re
import hashlib
import time
from pathlib import Path

from config import DIFFICULTY_PRESETS, LANES_2, LANES_4, LANES_6
from detector import detect_result
from audio_analyze import analyze_audio
from charter import Charter
from packager import build_chart_json, pack_pez, save_json


def _safe_stem(audio_stem: str) -> str:
    return "".join(c for c in audio_stem if c not in r'\/:*?"<>|')


def _parse_mix(spec: str) -> list:
    out = []
    for tok in (spec or "").split(";"):
        tok = tok.strip()
        if not tok:
            continue
        if "@" in tok:
            typ, when = tok.split("@", 1)
            out.append({"type": typ.strip(), "when": (when.strip() or "all")})
        else:
            out.append({"type": tok.strip(), "when": "all"})
    return out


def _build_line_fx(mode: str, sections: list, pulse_style: str = "chain",
                   deco_when: str = "intro_chorus", main_y: float = -300.0,
                   mix_spec: str = "", main_swing: bool = None,
                   sweep_flick_only: bool = False) -> dict:
    if not mode or mode == "none":
        return None
    cfg = {"mode": mode, "sections": sections, "main_y": float(main_y)}
    if main_swing is not None:
        cfg["main_swing"] = bool(main_swing)
    if sweep_flick_only:
        cfg["sweep_flick_only"] = True
    if mode in ("alpha_pulse", "pulse", "grid", "pinwheel", "curve", "color_flow",
                "glow", "bounce", "breathe", "meteor", "echo_trail", "spotlight"):
        cfg["alpha_pulse"] = True
    if mode in ("alpha_pulse", "pulse"):
        cfg["pulse_style"] = pulse_style or "chain"
    if mode == "pinwheel":
        cfg["deco"] = {"type": mode, "when": deco_when or "intro_chorus"}
    if mode == "curve":
        cfg["curve_when"] = deco_when or "climax"
    if mode == "mix":
        effects = _parse_mix(mix_spec)
        if not effects:
            effects = [
                {"type": "grid", "when": "all"},
                {"type": "sweep", "when": "all"},
                {"type": "pinwheel", "when": "climax"},
            ]
        cfg["effects"] = effects
        cfg["alpha_pulse"] = True
        cfg["lift"] = {"ease": 6, "up_y": 200.0, "transition_beats": 3.0}
    return cfg


def _safe_id(name: str) -> str:
    """生成纯 ASCII 的谱面 ID，避免导入器因非 ASCII/空格文件名丢失图片。"""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "song"
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:24]}_{digest}"


def generate(
    audio_path: str,
    difficulty: str = "hard",
    bpm: float = None,
    all_tiers: bool = False,
    image_path: str = None,
    title: str = None,
    artist: str = "",
    charter_name: str = None,
    outdir: str = None,
    density_mult: float = 1.0,
    line_fx: str = "none",
    pulse_style: str = "chain",
    deco_when: str = "intro_chorus",
    main_y: float = -300.0,
    mix_spec: str = "",
    key_mode: str = "auto",
    main_swing: bool = None,
    sweep_flick_only: bool = False,
    disable_drag: bool = False,
    tap_weight: float = None,
    hold_weight: float = None,
    flick_weight: float = None,
    drag_weight: float = None,
) -> dict:
    """返回 {tier: pez_path} 与日志文本。"""
    log = []
    started = time.perf_counter()
    audio_path = str(Path(audio_path))
    audio_stem = _safe_stem(Path(audio_path).stem)
    outdir = Path(outdir or Path(__file__).parent / "output")
    outdir.mkdir(parents=True, exist_ok=True)

    log.append("[1/3] 音频检测（节拍 / 音符起点）...")
    result = detect_result(audio_path, bpm=bpm)
    log.append(f"      踩音 {len(result['points'])} 点 | bpm={result['bpm']:.2f} | "
               f"offset={result['offset_sec']:.3f}s | duration={result['duration_sec']:.1f}s")

    log.append("[2/3] 音频分段落 / 频段分析 ...")
    audio = analyze_audio(audio_path, bpm=result["bpm"], duration_sec=result["duration_sec"])
    log.append(f"      段落 {len(audio['sections'])} | 已完成")

    name = (title or Path(audio_path).stem).strip()
    artist = artist or "Unknown"
    charter_name = charter_name or "audio2pez"

    tiers = list(DIFFICULTY_PRESETS.keys()) if all_tiers else [difficulty]
    results = {}
    for tier in tiers:
        log.append(f"[3/3] 生成难度 <{tier}> ...")
        presets = DIFFICULTY_PRESETS[tier]
        if key_mode == "2k":
            presets = dict(presets); presets["lanes"] = LANES_2
        elif key_mode == "4k":
            presets = dict(presets); presets["lanes"] = LANES_4
        elif key_mode == "6k":
            presets = dict(presets); presets["lanes"] = LANES_6
        if disable_drag:
            presets = dict(presets); presets["disable_drag"] = True; presets["drag_weight"] = 0.0
        if tap_weight is not None or hold_weight is not None or flick_weight is not None or drag_weight is not None:
            presets = dict(presets)
            if tap_weight is not None: presets["tap_weight"] = float(tap_weight)
            if hold_weight is not None: presets["hold_weight"] = float(hold_weight)
            if flick_weight is not None: presets["flick_weight"] = float(flick_weight)
            if drag_weight is not None: presets["drag_weight"] = float(drag_weight)
            if hold_weight is not None and float(hold_weight) <= 0.01: presets["disable_hold"] = True
            if drag_weight is not None and float(drag_weight) <= 0.01: presets["disable_drag"] = True

        charter = Charter(
            points=result["points"],
            bpm=result["bpm"],
            ticks_per_beat=result["ticks_per_beat"],
            bands=audio["bands"],
            onset_norm=audio["onset_norm"],
            sections=audio["sections"],
            difficulty=presets,
            rms_norm=audio["rms_norm"],
            density_mult=float(density_mult),
        )
        notes = charter.generate()
        log.append(f"      {presets['label']} {presets['level']}: {len(notes)} notes")

        chart_id = f"{_safe_id(name)}_{tier}"
        ext = Path(audio_path).suffix.lower() or ".mp3"
        mp3_name = f"{chart_id}{ext}"
        img_name = f"{chart_id}.png"
        meta = {
            "id": chart_id,
            "name": name,
            "level": f"{presets['label']} {presets['level']}",
            "charter": charter_name,
            "composer": artist,
            "illustration": artist or "",
            "song": mp3_name,
            "background": img_name,
            "offset": int(round(float(result["offset_sec"]) * 1000.0)),
            "duration": float(result["duration_sec"]),
        }
        line_fx_cfg = _build_line_fx(line_fx, audio["sections"], pulse_style, deco_when,
                                     main_y, mix_spec, main_swing, sweep_flick_only)
        chart = build_chart_json(
            notes, bpm=result["bpm"], meta=meta,
            tempo_events=result["tempo_events"], ticks_per_beat=result["ticks_per_beat"],
            line_fx=line_fx_cfg,
        )
        pez_path = pack_pez(audio_path, str(outdir), chart, image_path=image_path)
        save_json(chart, str(outdir))
        results[tier] = str(pez_path)

    elapsed = time.perf_counter() - started
    log.append(f"完成，耗时 {elapsed:.1f}s")
    return {"results": results, "log": "\n".join(log)}
