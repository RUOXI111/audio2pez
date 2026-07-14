"""
音频分析模块
- BPM / 节拍检测
- onset 检测 & 节拍对齐
- 频段能量分析
- 段落结构检测
"""

import numpy as np
import librosa
from config import *


def load_audio(filepath: str) -> tuple[np.ndarray, float]:
    """加载音频, 返回 (y, sr)"""
    print(f"[analyze] 加载音频: {filepath}")
    y, sr = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    duration = len(y) / sr
    print(f"[analyze]  采样率={sr}, 时长={duration:.1f}s, 样本数={len(y)}")
    return y, sr


def detect_bpm(y: np.ndarray, sr: float) -> float:
    """检测 BPM"""
    bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(bpm)
    print(f"[analyze] 检测到 BPM: {bpm:.1f}")
    return bpm


def detect_beats(y: np.ndarray, sr: float, bpm: float) -> np.ndarray:
    """
    检测节拍位置, 返回每拍的采样帧索引
    使用动态规划跟踪, 保证节拍均匀分布
    """
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, start_bpm=bpm, tightness=100)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    print(f"[analyze] 检测到 {len(beat_times)} 个节拍, 平均间隔 {np.mean(np.diff(beat_times))*1000:.1f}ms")
    return beat_times


def detect_onsets(y: np.ndarray, sr: float) -> tuple[np.ndarray, np.ndarray]:
    """
    检测 onset (音符起点)
    返回 (onset_times, onset_envelopes_per_band)
    """
    # 多频带 onset 检测
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP_LENGTH)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=HOP_LENGTH,
        delta=ONSET_SENSITIVITY,
        wait=HOP_LENGTH // 128,
        pre_max=3,
        post_max=3,
        pre_avg=3,
        post_avg=5,
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=HOP_LENGTH)
    print(f"[analyze] 检测到 {len(onset_times)} 个 onset")
    return onset_times, onset_env


def spectral_analysis(y: np.ndarray, sr: float) -> dict:
    """
    频段能量分析
    返回 {band_name: energy_curve} 时间轴对齐的频段能量
    """
    stft = np.abs(librosa.stft(y, hop_length=HOP_LENGTH))
    freqs = librosa.fft_frequencies(sr=sr)

    def band_energy(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        return np.mean(stft[mask], axis=0)

    bands = {
        "low":  band_energy(*BAND_LOW),
        "mid":  band_energy(*BAND_MID),
        "high": band_energy(*BAND_HIGH),
    }
    return bands


def get_dominant_band(bands: dict, frame_idx: int) -> str:
    """返回指定帧的主导频段"""
    values = {k: v[min(frame_idx, len(v)-1)] for k, v in bands.items()}
    return max(values, key=values.get)


def detect_sections(y: np.ndarray, sr: float, beat_times: np.ndarray) -> list:
    """
    检测歌曲段落结构
    基于 RMS 能量变化 + 节拍密度
    返回 [{start_beat, end_beat, label, density}]
    """
    rms = librosa.feature.rms(y=y, hop_length=HOP_LENGTH)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP_LENGTH)

    sections = []
    window_beats = SECTION_WINDOW
    for i in range(0, len(beat_times) - window_beats, window_beats):
        start_t = beat_times[i]
        end_t = beat_times[min(i + window_beats, len(beat_times) - 1)]

        # 窗口内的 RMS
        mask = (times >= start_t) & (times < end_t)
        avg_rms = np.mean(rms[mask]) if mask.any() else 0

        # 分类
        global_median = np.median(rms)
        if avg_rms < global_median * 0.6:
            label = "intro/break"
        elif avg_rms < global_median * 1.3:
            label = "verse"
        else:
            label = "chorus"

        # 密度 (从后面 generate 阶段填充)
        density = DENSITY_MID
        if label == "intro/break":
            density = DENSITY_LOW
        elif label == "chorus":
            density = DENSITY_HIGH

        sections.append({
            "start_beat": int(i),
            "end_beat": int(min(i + window_beats, len(beat_times) - 1)),
            "start_time": float(start_t),
            "end_time": float(end_t),
            "label": label,
            "density": density,
        })

    print(f"[analyze] 检测到 {len(sections)} 个段落:")
    for s in sections:
        print(f"  beat {s['start_beat']:3d}-{s['end_beat']:3d} | {s['label']:12s} | density={s['density']:.2f}")

    return sections
