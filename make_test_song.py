"""生成一段用于验证 audio2pez 链路的测试音频（纯标准库，无第三方依赖）。

128 BPM / 45 秒：底鼓踩四分音符、闭镲踩八分音符、五声音阶旋律。
"""
import array
import math
import random
import struct
import wave

SR = 44100
BPM = 128.0
BEAT = 60.0 / BPM
BARS = 24                     # 24 小节 * 4 拍 = 96 拍
DUR = BEAT * 4 * BARS

buf = array.array("d", [0.0]) * 0


def note(freq, dur, amp, kind="sine", attack=0.005, decay=6.0):
    n = int(dur * SR)
    out = []
    for i in range(n):
        t = i / SR
        env = (min(1.0, t / attack) if attack > 0 else 1.0) * math.exp(-decay * t)
        if kind == "sine":
            v = math.sin(2 * math.pi * freq * t)
        elif kind == "sq":
            v = 0.5 * math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * 2 * freq * t)
        else:  # noise
            v = random.uniform(-1, 1)
        out.append(v * env * amp)
    return out


def kick():
    n = int(0.18 * SR)
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-22.0 * t)
        f = 55.0 + 90.0 * math.exp(-35.0 * t)
        out.append(math.sin(2 * math.pi * f * t) * env * 0.85)
    return out


def hat():
    n = int(0.05 * SR)
    out = []
    for i in range(n):
        t = i / SR
        out.append(random.uniform(-1, 1) * math.exp(-70.0 * t) * 0.18)
    return out


n_total = int(DUR * SR) + SR
mix = [0.0] * n_total


def add(samples, at_sec, gain=1.0):
    start = int(at_sec * SR)
    for i, s in enumerate(samples):
        j = start + i
        if 0 <= j < n_total:
            mix[j] += s * gain


# 五声音阶（C 大调五声），高八度做主旋律
scale = [261.63, 293.66, 329.63, 392.00, 440.00,
         523.25, 587.33, 659.25, 783.99, 880.00]
random.seed(7)
melody = [random.choice(scale) for _ in range(BARS * 8)]

for bar in range(BARS):
    t0 = bar * 4 * BEAT
    for beat in range(4):
        add(kick(), t0 + beat * BEAT, 1.0)
        add(hat(), t0 + beat * BEAT + BEAT / 2, 1.0)
        add(hat(), t0 + beat * BEAT, 0.6)
    # 旋律走八分音符
    for k in range(8):
        f = melody[bar * 8 + k]
        add(note(f, BEAT * 0.9, 0.28, "sq", decay=5.0), t0 + k * BEAT / 2)

peak = max(abs(v) for v in mix) or 1.0
scale_gain = 0.89 / peak

pcm = array.array("h", (int(max(-1.0, min(1.0, v * scale_gain)) * 32767) for v in mix))
with wave.open("test_song.wav", "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

print("wrote test_song.wav  %.1fs  %d BPM  %d bars" % (DUR, BPM, BARS))
