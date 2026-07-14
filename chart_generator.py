"""
谱面生成模块 (v3 — 离散轨道 + 音色驱动)
核心改进:
- 使用离散轨道 (lanes) 而非连续位置
- 显著提高 Hold/Flick/Drag 比例
- 频段驱动轨道选择，而非随机
"""

import math
import random
import numpy as np
from config import *


# ─────────────────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────────────────

def time_to_beats(time_sec: float, bpm: float) -> float:
    return time_sec * bpm / 60.0


def beat_to_triplet(beat_pos: float, quantize: int = BEAT_QUANTIZE) -> list:
    den = quantize
    bar = int(beat_pos)
    fractional = beat_pos - bar
    num_raw = round(fractional * den)
    if num_raw == 0:
        return [bar, 0, 1]
    g = math.gcd(num_raw, den)
    return [bar, num_raw // g, den // g]


def get_dominant_band(bands: dict, frame_idx: int) -> str:
    values = {k: v[min(frame_idx, len(v)-1)] for k, v in bands.items()}
    return max(values, key=values.get)


# ─────────────────────────────────────────────────────
#  主生成器
# ─────────────────────────────────────────────────────

class ChartGenerator:
    def __init__(self, bpm: float, beat_times: np.ndarray,
                 onset_env: np.ndarray, bands: dict, sections: list,
                 difficulty: dict,
                 sr: float = SAMPLE_RATE):
        self.bpm = bpm
        self.beat_times = beat_times
        self.onset_env = onset_env
        self.bands = bands
        self.sections = sections
        self.difficulty = difficulty
        self.sr = sr

        # 难度感知的轨道组
        self._active_lanes = self.difficulty["lanes"]
        self._min_note_gap = self.difficulty.get("min_note_gap", MIN_NOTE_GAP)

        # 构建密集节拍网格
        self.grid = self._build_grid()
        print(f"[chart_generator] 难度: {self.difficulty['level_tag']}, "
              f"节拍网格: {len(self.grid)} 个格点 ({GRID_DIVISION} 分音), "
              f"轨道: {len(self._active_lanes)} 轨")

        # 归一化 onset envelope
        env_max = np.max(self.onset_env) if len(self.onset_env) > 0 else 1.0
        self.onset_norm = self.onset_env / max(env_max, 0.001)

        # 轨道使用记录: 跟踪每个轨道的最近使用时间, 避免过度重复
        self._lane_cooldown = {lane: -999.0 for lane in self._active_lanes}

    # ── 网格 ──────────────────────────────────────

    def _build_grid(self) -> np.ndarray:
        if len(self.beat_times) < 2:
            return np.array([])
        beat_interval = 60.0 / self.bpm
        sub_interval = beat_interval / GRID_DIVISION
        start = self.beat_times[0]
        end = self.beat_times[-1] + beat_interval
        return np.arange(start, end, sub_interval)

    def _get_onset_strength(self, time_sec: float) -> float:
        frame = int(time_sec * self.sr / HOP_LENGTH)
        if 0 <= frame < len(self.onset_norm):
            return float(self.onset_norm[frame])
        return 0.0

    # ── 延音检测 ──────────────────────────────────

    def _detect_sustain(self, time_sec: float) -> float:
        """
        检测 onset 后的能量持续时间 (秒).
        返回延音时长: 0=短促(Tap), >0.1=有延音(Hold候选)

        原理: 在 onset 之后查看 onset envelope 是否持续高于阈值,
        如果持续多个帧, 说明这是一个持续音 (人声长音、弦乐等) 而非短促打击音
        """
        start_frame = int(time_sec * self.sr / HOP_LENGTH)
        env = self.onset_norm
        if start_frame >= len(env):
            return 0.0

        sustain_frames = 0
        gap_frames = 0
        for offset in range(1, min(32, len(env) - start_frame)):
            val = env[start_frame + offset]
            if val >= SUSTAIN_THRESHOLD:
                sustain_frames += 1
                gap_frames = 0
            else:
                gap_frames += 1
                if gap_frames > SUSTAIN_MAX_GAP:
                    break

        sustain_sec = sustain_frames * HOP_LENGTH / self.sr
        return sustain_sec

    def _is_sustained(self, time_sec: float) -> bool:
        """判断是否有足够的延音来触发 Hold"""
        return self._detect_sustain(time_sec) >= (SUSTAIN_MIN_FRAMES * HOP_LENGTH / self.sr)

    # ── 轨道选择 ──────────────────────────────────

    def _pick_lane(self, time_sec: float) -> float:
        """频段驱动轨道选择, 动态适配轨道数量"""
        frame = int(time_sec * self.sr / HOP_LENGTH)
        band = get_dominant_band(self.bands, frame)
        n_lanes = len(self._active_lanes)

        # 根据轨道数生成权重: 低频偏内, 高频偏外, 中频均匀
        half = n_lanes / 2
        if band == "low":
            # 低频: 越靠近中心权重越高 (钟形)
            weights = np.array([2.0 - abs(i - half + 0.5) / half for i in range(n_lanes)], dtype=float)
        elif band == "high":
            # 高频: 越远离中心权重越高
            weights = np.array([1.0 + abs(i - half + 0.5) / half for i in range(n_lanes)], dtype=float)
        else:
            # 中频: 均匀
            weights = np.ones(n_lanes, dtype=float)

        # Cooldown: 最近用过的轨道降低权重
        for i, lane in enumerate(self._active_lanes):
            if time_sec - self._lane_cooldown[lane] < 0.3:
                weights[i] *= 0.2
        if weights.sum() < 0.01:
            weights = np.ones(n_lanes, dtype=float)

        weights /= weights.sum()
        idx = int(np.random.choice(n_lanes, p=weights))
        lane = self._active_lanes[idx]
        self._lane_cooldown[lane] = time_sec
        return float(lane)

    # ── 音符类型 ──────────────────────────────────

    def _classify_type(self, time_sec: float) -> int:
        """
        音乐驱动的音符类型分类 (v2):
        - 长延音 (>150ms) → Hold  (人声长音、弦乐、合成器)
        - 强重音 + 无延音  → Flick (军鼓重击、镲片、强调拍)
        - 高频滑动音       → Drag  (合成器滑音、滤波器扫频)
        - 其余普通音       → Tap   (底鼓、基本节拍、旋律音)

        最终按 difficulty 的 target weights 归一化,
        保证整体分布趋近目标占比。"""
        strength = self._get_onset_strength(time_sec)
        frame = int(time_sec * self.sr / HOP_LENGTH)
        band = get_dominant_band(self.bands, frame)
        sustain_sec = self._detect_sustain(time_sec)
        is_sustained = sustain_sec > 0.15  # >150ms = 明显延音

        diff = self.difficulty

        # 1. HOLD: 明显延音 → 持续音
        if is_sustained:
            if random.random() < 0.80:
                return 2  # Hold

        # 2. FLICK: 强重音 (高 onset 强度, 特别是中高频)
        #    军鼓、镲片、强调拍 → 用 Flick 表现力度
        is_accent = (strength > 0.35) or (strength > 0.20 and band == "high")
        if is_accent and not is_sustained:
            if random.random() < 0.60:
                return 3  # Flick

        # 3. DRAG: 高频 + 短延音 → 滑动感
        #    合成器滑音、滤波器扫频
        if band == "high" and sustain_sec > 0.08 and not is_sustained:
            if random.random() < 0.40:
                return 4  # Drag

        # 4. 按目标权重随机分配 (用于没有明显音乐特征的普通音符)
        tw = diff["tap_weight"]
        fw = tw + diff["flick_weight"]
        dw = fw + diff["drag_weight"]
        # hw = dw + diff["hold_weight"] = 1.0

        r = random.random()
        if r < tw:
            return 1  # Tap
        elif r < fw:
            return 3  # Flick
        elif r < dw:
            return 4  # Drag
        else:
            return 2  # Hold

    # ── 单音符构造 ────────────────────────────────

    def _make_note(self, time_sec: float, note_type: int,
                   lane: float = None) -> dict:
        beat_val = time_to_beats(time_sec, self.bpm)
        quantized = round(beat_val * BEAT_QUANTIZE) / BEAT_QUANTIZE
        triplet = beat_to_triplet(quantized)

        if lane is None:
            lane = self._pick_lane(time_sec)

        end_triplet = triplet.copy()
        # Hold: 根据延音长度选择持续时间
        if note_type == 2:
            sustain_sec = self._detect_sustain(time_sec)
            if sustain_sec > 0.5:
                # 长延音 → 长 Hold
                candidates = [b for b in HOLD_BEATS_TIER if b <= HOLD_MAX_BEATS and b >= 0.5]
            elif sustain_sec > 0.2:
                # 中等延音
                candidates = [0.25, 0.375, 0.5, 0.75]
            else:
                # 短延音 (靠概率选了 Hold 但实际不长)
                candidates = [0.25, 0.375]
            hold_beats = random.choice(candidates)
            hold_beats = min(hold_beats, HOLD_MAX_BEATS)
            end_beat = quantized + hold_beats
            end_triplet = beat_to_triplet(end_beat)

        return {
            "above": 1,
            "alpha": DEFAULT_ALPHA,
            "endTime": end_triplet,
            "isFake": 0,
            "positionX": round(lane, 1),
            "size": DEFAULT_SIZE,
            "speed": 1.0,
            "startTime": triplet,
            "type": note_type,
            "visibleTime": 999999.0,
            "yOffset": 0.0,
        }

    # ── 模式库 ────────────────────────────────────

    def _pick_pattern(self, label: str) -> str:
        """难度感知的 pattern 选择: easy 避免复杂指法"""
        if label == "intro/break":
            style = "sparse"
        elif label == "chorus":
            style = "syncopated"
        else:
            style = "even"

        weights = dict(PATTERN_WEIGHTS[style])
        diff = self.difficulty

        # Easy 难度: 移除 burst 和 stair (复杂指法)
        if diff.get("burst_prob", 0.5) < 0.1:
            weights.pop("burst", None)
        if diff.get("stair_prob", 0.25) < 0.1:
            weights.pop("stair", None)

        # 重归一化
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        return random.choices(list(weights.keys()), weights=list(weights.values()))[0]

    def _apply_stair(self, items: list) -> list[dict]:
        """楼梯: 轨道逐级递进, 碰壁折返"""
        notes = []
        lanes = self._active_lanes
        n_lanes = len(lanes)
        direction = random.choice([1, -1])
        idx = random.randint(0, n_lanes - 1)  # 随机起点
        for gt, _ in items:
            idx = max(0, min(n_lanes - 1, idx))
            lane = lanes[idx]
            idx += direction
            # 碰壁折返
            if idx >= n_lanes:
                idx = n_lanes - 2
                direction = -1
            elif idx < 0:
                idx = 1
                direction = 1
            ntype = self._classify_type(gt)
            notes.append(self._make_note(gt, ntype, lane=lane))
        return notes

    def _apply_mirror(self, items: list) -> list[dict]:
        """对称: 前半左侧, 后半右侧, 中点随机"""
        notes = []
        lanes = self._active_lanes
        mid_lane = len(lanes) // 2
        left_set = lanes[:mid_lane]
        right_set = lanes[mid_lane:]
        n = len(items)
        mid = n // 2
        for i, (gt, _) in enumerate(items):
            if i < mid:
                lane = random.choice(left_set)
            elif i == mid:
                lane = random.choice(lanes)
            else:
                lane = random.choice(right_set)
            ntype = self._classify_type(gt)
            notes.append(self._make_note(gt, ntype, lane=lane))
        return notes

    def _apply_alternate(self, items: list) -> list[dict]:
        """交替: 左右两侧交替"""
        notes = []
        lanes = self._active_lanes
        mid = len(lanes) // 2
        left_lanes = lanes[:mid]
        right_lanes = lanes[mid:]
        left_idx = right_idx = 0
        for i, (gt, _) in enumerate(items):
            if i % 2 == 0:
                lane = left_lanes[left_idx % len(left_lanes)]
                left_idx += 1
            else:
                lane = right_lanes[right_idx % len(right_lanes)]
                right_idx += 1
            ntype = self._classify_type(gt)
            notes.append(self._make_note(gt, ntype, lane=lane))
        return notes

    def _apply_flow(self, items: list) -> list[dict]:
        """流水: 正弦波扫描所有轨道"""
        notes = []
        lanes = self._active_lanes
        n = len(items)
        if n < 2:
            return self._apply_alternate(items)
        max_x = max(abs(l) for l in lanes)
        for i, (gt, _) in enumerate(items):
            phase = i / max(n - 1, 1) * math.pi * 2 + random.uniform(-0.3, 0.3)
            raw = max_x * math.sin(phase)
            lane = min(lanes, key=lambda x: abs(x - raw))
            ntype = self._classify_type(gt)
            notes.append(self._make_note(gt, ntype, lane=lane))
        return notes

    def _apply_burst(self, items: list) -> list[dict]:
        """爆发: 双押/多押 — 每个时间点 2 个音符在不同轨道"""
        notes = []
        lanes = self._active_lanes
        n_lanes = len(lanes)
        for gt, _ in items:
            ntype = self._classify_type(gt)
            idx1 = random.randrange(n_lanes)
            gap = max(2, n_lanes // 3)  # 确保间隔至少 1/3 轨道数
            idx2 = (idx1 + random.randint(gap, n_lanes - gap)) % n_lanes
            notes.append(self._make_note(gt, ntype, lane=lanes[idx1]))
            notes.append(self._make_note(gt, ntype, lane=lanes[idx2]))
        return notes

    def _apply_random(self, items: list) -> list[dict]:
        """随机轨道: 频段加权随机"""
        notes = []
        for gt, _ in items:
            ntype = self._classify_type(gt)
            lane = self._pick_lane(gt)
            notes.append(self._make_note(gt, ntype, lane=lane))
        return notes

    # ── 模式分发 ──────────────────────────────────

    def _gen_pattern_notes(self, grid_times: np.ndarray, pattern: str) -> list[dict]:
        items = list(zip(grid_times, [0] * len(grid_times)))
        dispatch = {
            "stair":     self._apply_stair,
            "mirror":    self._apply_mirror,
            "alternate": self._apply_alternate,
            "flow":      self._apply_flow,
            "burst":     self._apply_burst,
            "random":    self._apply_random,
        }
        fn = dispatch.get(pattern, self._apply_alternate)
        return fn(items)

    # ── 主生成流程 ──────────────────────────────────

    def generate(self) -> list[dict]:
        print(f"\n[chart_generator] 开始生成谱面 (难度: {self.difficulty['level_tag']}, "
              f"{len(self._active_lanes)} 轨模式)...")

        all_notes = []
        diff = self.difficulty

        for section in self.sections:
            start_t = section["start_time"]
            end_t = section["end_time"]
            label = section["label"]
            density = section["density"]

            mask = (self.grid >= start_t) & (self.grid < end_t)
            section_grid = self.grid[mask]
            if len(section_grid) == 0:
                continue

            # 按 onset 强度排序, 取 top-K
            scored = []
            for gt in section_grid:
                s = self._get_onset_strength(gt)
                if s >= NOTE_MIN_STRENGTH:
                    scored.append((gt, s))

            if len(scored) == 0:
                continue

            scored.sort(key=lambda x: -x[1])
            # 密度 = 段落密度 × difficulty.density_mult
            k = max(3, int(len(scored) * min(density * diff["density_mult"], 1.0)))
            k = min(k, len(scored))
            top = scored[:k]
            top.sort(key=lambda x: x[0])
            selected_times = np.array([x[0] for x in top])

            pattern = self._pick_pattern(label)
            notes = self._gen_pattern_notes(selected_times, pattern)

            if notes:
                tcounts = {}
                for n in notes:
                    t = n['type']
                    tcounts[t] = tcounts.get(t, 0) + 1
                tn = {1:'T',2:'H',3:'F',4:'D'}
                details = ','.join(f"{tn[t]}:{c}" for t,c in sorted(tcounts.items()))
                print(f"  {label:12s} | grid={len(scored):3d}→top={k:3d}→{len(notes):3d} notes | {pattern:10s} [{details}]")
                all_notes.extend(notes)

        all_notes.sort(key=lambda n: n["startTime"][0] + n["startTime"][1] / max(n["startTime"][2], 1))

        types = {}
        for n in all_notes:
            t = n['type']
            types[t] = types.get(t, 0) + 1
        tn_full = {1:"Tap", 2:"Hold", 3:"Flick", 4:"Drag"}
        print(f"[chart_generator] 共 {len(all_notes)} 音符: " +
              ", ".join(f"{tn_full[t]}:{c}" for t, c in sorted(types.items())))

        # 轨道分布
        lane_dist = {}
        for n in all_notes:
            l = n['positionX']
            lane_dist[l] = lane_dist.get(l, 0) + 1
        print(f"[chart_generator] 轨道分布: " +
              ", ".join(f"{k:.0f}:{v}" for k, v in sorted(lane_dist.items())))

        return all_notes

    def generate_events(self) -> list[dict]:
        """生成事件层, 包含开场判定线下移动画"""
        # 开场: 判定线从下方 Y=INTRO_LINE_Y 移动到 Y=0
        intro_end_beat = beat_to_triplet(INTRO_DURATION)

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
            # ── 开场动画: Y 从 -400 升到 0 ──
            "moveYEvents": [
                {
                    "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
                    "easingLeft": 0.0, "easingRight": 1.0,
                    "easingType": INTRO_EASING,       # 24 = ease-out, 先快后慢
                    "end": 0.0,                        # 目标位置 (正常)
                    "start": float(INTRO_LINE_Y),      # 起始位置 (下方)
                    "endTime": intro_end_beat,          # 动画结束拍
                    "startTime": [0, 0, 1],            # 动画开始拍
                    "linkgroup": 0,
                },
                # 之后保持不变
                {
                    "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
                    "easingLeft": 0.0, "easingRight": 1.0, "easingType": 1,
                    "end": 0.0, "start": 0.0,
                    "endTime": [999999, 0, 1],
                    "startTime": intro_end_beat,
                    "linkgroup": 0,
                },
            ],
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
