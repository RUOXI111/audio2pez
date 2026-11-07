# -*- coding: utf-8 -*-
"""音频分析：频段能量 / onset 包络 / RMS 分段。BPM 由检测模块提供，此处不重复测速。"""

import numpy as np
import librosa

from config import (
    SAMPLE_RATE, HOP_LENGTH,
    BAND_LOW, BAND_MID, BAND_HIGH,
    SECTION_WINDOW, DENSITY_LOW, DENSITY_MID, DENSITY_HIGH,
)


def load_audio(path: str) -> tuple[np.ndarray, float]:
    y, sr = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    return y, sr


def get_dominant_band(bands: dict, frame_idx: int) -> str:
    values = {k: v[min(frame_idx, len(v) - 1)] for k, v in bands.items()}
    return max(values, key=values.get)


def analyze_audio(path: str, bpm: float, duration_sec: float, chorus_ranges=None) -> dict:
    """返回 dict: y / onset_norm / bands / rms / times / sections。

    chorus_ranges: 可选 [(start_sec, end_sec), ...]，手动指定副歌区间（覆盖自动判断）。
    """
    y, sr = load_audio(path)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    env_max = float(onset_env.max()) if len(onset_env) else 1.0
    onset_norm = onset_env / max(env_max, 0.001)

    stft = np.abs(librosa.stft(y, hop_length=HOP_LENGTH))
    freqs = librosa.fft_frequencies(sr=sr)

    def band_energy(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return np.mean(stft[mask], axis=0)

    bands = {
        "low": band_energy(*BAND_LOW),
        "mid": band_energy(*BAND_MID),
        "high": band_energy(*BAND_HIGH),
    }

    rms = librosa.feature.rms(y=y, hop_length=HOP_LENGTH)[0]
    rms_max = float(rms.max()) if len(rms) else 1.0
    rms_norm = (rms / max(rms_max, 0.001)).astype(float)
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP_LENGTH)

    sections = _detect_sections(rms, times, duration_sec, bpm, chorus_ranges)
    return {
        "y": y, "sr": sr, "onset_norm": onset_norm,
        "bands": bands, "rms": rms, "rms_norm": rms_norm, "times": times, "sections": sections,
    }


_LABELS = [("intro/break", DENSITY_LOW), ("verse", DENSITY_MID), ("chorus", DENSITY_HIGH)]


def parse_time_ranges(spec) -> list:
    """解析 "51.3-85.5, 2:22.6-2:57.5" → [(51.3, 85.5), (142.6, 177.5)]。支持秒或 分:秒。"""
    if not spec:
        return []
    if isinstance(spec, (list, tuple)):
        return sorted((float(a), float(b)) for a, b in spec if float(b) > float(a))

    def sec(tok: str) -> float:
        tok = tok.strip()
        if ":" in tok:
            m, s = tok.rsplit(":", 1)
            return float(m) * 60.0 + float(s)
        return float(tok)

    out = []
    for part in str(spec).replace("，", ",").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            raise ValueError(f"区间格式应为 起-止，例如 51.3-85.5 或 0:51.3-1:25.5：{part!r}")
        a, b = part.split("-", 1)
        a, b = sec(a), sec(b)
        if b <= a:
            raise ValueError(f"区间结束必须晚于开始：{part!r}")
        out.append((a, b))
    return sorted(out)


def _detect_sections(rms, times, duration_sec: float, bpm: float, chorus_ranges=None) -> list:
    """按拍数窗口把歌曲分成 intro/verse/chorus，返回含密度信息的段落列表。

    自动模式：按 RMS 相对全曲中位数分级，再去掉"孤立的单窗口跳变"，避免副歌里夹一格主歌。
    手动模式（chorus_ranges）：段落边界对齐到给定区间，区间内一律 chorus，区间外最多 verse。
    """
    if bpm <= 0:
        bpm = 120.0
    window_sec = SECTION_WINDOW * 60.0 / bpm
    median = float(np.median(rms)) if len(rms) else 0.0

    def level(start_t, end_t) -> int:
        mask = (times >= start_t) & (times < end_t)
        avg = float(np.mean(rms[mask])) if mask.any() else 0.0
        if median > 0 and avg < median * 0.6:
            return 0
        if median > 0 and avg < median * 1.3:
            return 1
        return 2

    def make(start_t, end_t, lv):
        label, density = _LABELS[lv]
        return {"start_time": start_t, "end_time": end_t, "label": label, "density": density}

    ranges = parse_time_ranges(chorus_ranges)
    if ranges:
        cuts = {0.0, float(duration_sec)}
        for a, b in ranges:
            cuts.update((min(max(a, 0.0), duration_sec), min(max(b, 0.0), duration_sec)))
        cuts = sorted(cuts)
        sections = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            if b - a < 1e-3:
                continue
            mid = (a + b) / 2.0
            in_chorus = any(ra <= mid < rb for ra, rb in ranges)
            n = max(1, int(round((b - a) / window_sec)))
            step = (b - a) / n
            for k in range(n):
                s, e = a + k * step, (a + (k + 1) * step) if k < n - 1 else b
                lv = 2 if in_chorus else min(level(s, e), 1)
                sections.append(make(s, e, lv))
        return sections

    n = max(1, int(np.ceil(duration_sec / window_sec)))
    bounds = [(i * window_sec, min((i + 1) * window_sec, duration_sec)) for i in range(n)]
    lv = [level(s, e) for s, e in bounds]
    # 去掉孤立跳变：前后两格一致而中间一格不同 → 跟随前后
    for i in range(1, n - 1):
        if lv[i - 1] == lv[i + 1] != lv[i]:
            lv[i] = lv[i - 1]
    return [make(s, e, l) for (s, e), l in zip(bounds, lv)]