# -*- coding: utf-8 -*-
"""构建 RPE chart JSON 并打包 .pez (ZIP)。判定线 isCover/posControl/yControl 固定，避免非 Hold 音符居中。"""

import os
import json
import math
import zipfile
import struct
import zlib

from config import RPE_VERSION, DEFAULT_SPEED
from line_fx import apply_line_fx, _incline_placeholder


def _frac_time(tick: int, ticks_per_beat: int) -> list[int]:
    tick = max(0, int(tick))
    tpb = int(ticks_per_beat or 480)
    whole, rem = divmod(tick, tpb)
    if rem == 0:
        return [whole, 0, 1]
    g = math.gcd(rem, tpb)
    return [whole, rem // g, tpb // g]


def build_bpm_list(bpm: float, tempo_events=None, ticks_per_beat: int = 480) -> list:
    if tempo_events:
        out = []
        tpb = int(ticks_per_beat or 480)
        for ev in tempo_events:
            out.append({
                "startTime": _frac_time(ev.get("beat_tick", 0), tpb),
                "bpm": float(ev.get("bpm", bpm)),
            })
        # 去重：同一 tick 只保留一次
        seen, dedup = set(), []
        for item in out:
            key = tuple(item["startTime"])
            if key not in seen:
                seen.add(key)
                dedup.append(item)
        return dedup or [{"startTime": [0, 0, 1], "bpm": float(bpm)}]
    return [{"startTime": [0, 0, 1], "bpm": float(bpm)}]


def _merge_extended(extra=None):
    """主判定线 extended 合并（保留 inclineEvents 垫底）。"""
    base = {"inclineEvents": [_incline_placeholder()]}
    if isinstance(extra, dict):
        for k, v in extra.items():
            if v:
                base[k] = v
    return base


def build_chart_json(notes: list, bpm: float, meta: dict,
                     tempo_events=None, ticks_per_beat: int = 480,
                     line_fx=None) -> dict:
    main_events, extra_lines, main_notes, main_extended = apply_line_fx(
        line_fx, notes, bpm, int(ticks_per_beat or 480), DEFAULT_SPEED)
    if main_events is None:
        main_events = _default_events()

    main_line = {
        "Group": 0, "Name": "主判定线", "Texture": "line.png",
        "alphaControl": [
            {"alpha": 1.0, "easing": 1, "x": 0.0},
            {"alpha": 1.0, "easing": 1, "x": 9999999.0},
        ],
        "bpmfactor": 1.0,
        "eventLayers": main_events,
        "extended": _merge_extended(main_extended), "father": -1,
        "isCover": 1,
        "notes": main_notes, "numOfNotes": len(main_notes),
        "posControl": [
            {"easing": 1, "pos": 1.0, "x": 0.0},
            {"easing": 1, "pos": 1.0, "x": 9999999.0},
        ],
        "sizeControl": [
            {"easing": 1, "size": 1.0, "x": 0.0},
            {"easing": 1, "size": 1.0, "x": 9999999.0},
        ],
        "skewControl": [
            {"easing": 1, "skew": 0.0, "x": 0.0},
            {"easing": 1, "skew": 0.0, "x": 9999999.0},
        ],
        "yControl": [
            {"easing": 1, "x": 0.0, "y": 1.0},
            {"easing": 1, "x": 9999999.0, "y": 1.0},
        ],
        "zOrder": 0,
    }

    chart = {
        "BPMList": build_bpm_list(bpm, tempo_events, ticks_per_beat),
        "META": {
            "RPEVersion": RPE_VERSION,
            "background": meta.get("background", "background.jpg"),
            "charter": meta.get("charter", "auto-generated"),
            "composer": meta.get("composer", "Unknown"),
            "illustration": meta.get("illustration", ""),
            "id": meta.get("id", "0"),
            "level": meta.get("level", "HARD"),
            "name": meta.get("name", "output"),
            "offset": int(meta.get("offset", 0)),
            "song": meta.get("song", "audio.mp3"),
            "duration": float(meta.get("duration") or 0.0),
        },
        "judgeLineGroup": ["Default"],
        "judgeLineList": [main_line] + list(extra_lines),
    }
    return chart


def _default_events() -> list:
    return [{
        "alphaEvents": [{
            "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
            "easingLeft": 0.0, "easingRight": 1.0, "easingType": 1,
            "end": 255, "start": 255,
            "endTime": [999999, 0, 1], "startTime": [0, 0, 1], "linkgroup": 0,
        }],
        "moveXEvents": [{
            "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
            "easingLeft": 0.0, "easingRight": 1.0, "easingType": 1,
            "end": 0.0, "start": 0.0,
            "endTime": [999999, 0, 1], "startTime": [0, 0, 1], "linkgroup": 0,
        }],
        "moveYEvents": [{
            "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
            "easingLeft": 0.0, "easingRight": 1.0, "easingType": 1,
            "end": 0.0, "start": 0.0,
            "endTime": [999999, 0, 1], "startTime": [0, 0, 1], "linkgroup": 0,
        }],
        "rotateEvents": [{
            "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
            "easingLeft": 0.0, "easingRight": 1.0, "easingType": 1,
            "end": 0.0, "start": 0.0,
            "endTime": [999999, 0, 1], "startTime": [0, 0, 1], "linkgroup": 0,
        }],
        "speedEvents": [{
            "end": DEFAULT_SPEED, "start": DEFAULT_SPEED,
            "endTime": [999999, 0, 1], "startTime": [0, 0, 1], "linkgroup": 0,
        }],
    }]


def pack_pez(audio_path: str, output_dir: str, chart_json: dict, image_path: str = None) -> str:
    meta = chart_json["META"]
    chart_id = meta["id"]
    json_name = f"{chart_id}.json"
    mp3_name = meta["song"]
    img_name = meta["background"]
    pez_name = f"{chart_id}.pez"

    os.makedirs(output_dir, exist_ok=True)
    pez_path = os.path.join(output_dir, pez_name)

    with zipfile.ZipFile(pez_path, "w", zipfile.ZIP_DEFLATED) as zf:
        json_str = json.dumps(chart_json, ensure_ascii=False, indent=2)
        zf.writestr(json_name, json_str)

        if audio_path and os.path.exists(audio_path):
            zf.write(audio_path, mp3_name)

        if image_path and os.path.exists(image_path):
            zf.writestr(img_name, _image_to_png_bytes(image_path))
        else:
            zf.writestr(img_name, _placeholder_png())

        info = (
            "#\n"
            f"Name: {meta['name']}\n"
            f"Path: {chart_id}\n"
            f"Song: {mp3_name}\n"
            f"Picture: {img_name}\n"
            f"Chart: {json_name}\n"
            f"Level: {meta['level']}\n"
            f"Composer: {meta['composer']}\n"
            f"Charter: {meta['charter']}\n"
        )
        zf.writestr("info.txt", info)

    return pez_path


def save_json(chart_json: dict, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{chart_json['META']['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chart_json, f, ensure_ascii=False, indent=2)
    return path


def _placeholder_png() -> bytes:
    """生成一张 1280x720 深色占位图，避免 Phira 判定 'no picture'（1x1 会被当成无图）。"""
    from PIL import Image
    import io
    img = Image.new("RGB", (1280, 720), (30, 24, 70))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _image_to_png_bytes(path: str) -> bytes:
    """把任意封面统一转成 PNG 字节（扩展名永远与内容匹配）。失败则回退占位图。"""
    from PIL import Image
    import io
    try:
        img = Image.open(path).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return _placeholder_png()
