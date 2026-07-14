"""
PEZ 打包模块
将 JSON + 音频 + 图片打包为 .pez (ZIP) 文件
"""

import os
import json
import zipfile
import shutil
from config import *


def build_chart_json(bpm: float, notes: list[dict], events: list[dict],
                     meta: dict) -> dict:
    """
    构建完整的 RPE 格式 JSON 对象
    """
    # 主判定线
    main_line = {
        "Group": 0,
        "Name": "主判定线",
        "Texture": "line.png",
        "alphaControl": [
            {"alpha": 1.0, "easing": 1, "x": 0.0},
            {"alpha": 1.0, "easing": 1, "x": 9999999.0},
        ],
        "bpmfactor": 1.0,
        "eventLayers": events if events else _default_events(),
        "extended": {},
        "father": -1,
        "isCover": True,
        "notes": notes,
        "numOfNotes": len(notes),
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
        "BPMList": [
            {"bpm": bpm, "startTime": [0, 0, 1]}
        ],
        "META": {
            "RPEVersion": RPE_VERSION,
            "background": meta.get("background", "background.jpg"),
            "charter": meta.get("charter", "auto-generated"),
            "composer": meta.get("composer", "Unknown"),
            "id": meta.get("id", "0"),
            "level": meta.get("level", "IN 13"),
            "name": meta.get("name", "output"),
            "offset": meta.get("offset", 0),
            "song": meta.get("song", "audio.mp3"),
        },
        "judgeLineGroup": ["Default"],
        "judgeLineList": [main_line],
    }

    return chart


def _default_events() -> list:
    """默认事件层"""
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


def pack_pez(audio_path: str, output_dir: str, chart_json: dict,
             image_path: str = None) -> str:
    """
    将谱面 JSON + 音频打包为 .pez 文件
    返回输出文件路径
    """
    meta = chart_json["META"]
    chart_id = meta["id"]
    json_name = f"{chart_id}.json"
    mp3_name = meta["song"]
    img_name = meta["background"]
    pez_name = f"{chart_id}.pez"

    os.makedirs(output_dir, exist_ok=True)

    # 构建 .pez 包
    pez_path = os.path.join(output_dir, pez_name)
    print(f"\n[packager] 打包 → {pez_path}")

    with zipfile.ZipFile(pez_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # JSON
        json_str = json.dumps(chart_json, ensure_ascii=False, indent=2)
        zf.writestr(json_name, json_str)
        print(f"  + {json_name} ({len(json_str):,} bytes)")

        # MP3
        if os.path.exists(audio_path):
            zf.write(audio_path, mp3_name)
            mp3_size = os.path.getsize(audio_path)
            print(f"  + {mp3_name} ({mp3_size:,} bytes)")

        # 图片
        if image_path and os.path.exists(image_path):
            zf.write(image_path, img_name)
            img_size = os.path.getsize(image_path)
            print(f"  + {img_name} ({img_size:,} bytes)")
        else:
            # 如果没有图片, 创建一个 1x1 黑色占位 PNG
            placeholder = _make_placeholder_png()
            zf.writestr(img_name, placeholder)
            print(f"  + {img_name} (placeholder)")

        # info.txt
        info = (
            f"#\n"
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
        print(f"  + info.txt")

    pez_size = os.path.getsize(pez_path)
    print(f"[packager] 完成! {pez_path} ({pez_size:,} bytes)")
    return pez_path


def save_json(chart_json: dict, output_dir: str) -> str:
    """单独保存 JSON (方便调试)"""
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{chart_json['META']['id']}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(chart_json, f, ensure_ascii=False, indent=2)
    print(f"[packager] JSON 已保存 → {json_path}")
    return json_path


def _make_placeholder_png() -> bytes:
    """生成 1x1 黑色 PNG (最小有效 PNG)"""
    import struct
    import zlib

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b'\x00\x00\x00')
    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', ihdr)
        + chunk(b'IDAT', raw)
        + chunk(b'IEND', b'')
    )
